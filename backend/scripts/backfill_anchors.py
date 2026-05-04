"""One-shot backfill of positive/negative anchors from historical Rating rows.

Usage:
    cd backend
    python -m scripts.backfill_anchors --dry-run       # preview, no commit
    python -m scripts.backfill_anchors                  # apply for all users
    python -m scripts.backfill_anchors --user-id <uuid> # apply for one user

Safely re-runnable (idempotent). Never touches source="reference" entries.
"""

import argparse
import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def backfill_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    dry_run: bool,
) -> dict:
    """Backfill anchors for one user from their Rating rows.

    Returns a summary dict with counts.
    """
    from app.models.rating import Rating
    from app.models.paper import Paper
    from app.models.user_profile import UserProfile
    from app.routers.ratings import feedback_to_anchor_spec

    # Fetch profile
    profile = (await session.execute(
        select(UserProfile).where(UserProfile.id == user_id)
    )).scalar_one_or_none()
    if not profile:
        return {"error": f"User {user_id} not found"}

    # Fetch all ratings with paper embeddings, newest first
    result = await session.execute(
        select(Rating, Paper.embedding)
        .join(Paper, Rating.paper_id == Paper.id)
        .where(Rating.user_id == user_id)
        .order_by(Rating.rated_at.desc())
    )
    rows = result.all()

    # Track existing reference paper_ids in current anchors
    existing_positive = list(profile.positive_anchors or [])
    existing_negative = list(profile.negative_anchors or [])
    reference_ids = {
        a["paper_id"] for a in existing_positive if a.get("source") == "reference"
    }
    existing_rating_ids_pos = {
        a["paper_id"] for a in existing_positive if a.get("source") == "rating"
    }
    existing_rating_ids_neg = {
        a["paper_id"] for a in existing_negative if a.get("source") == "rating"
    }

    skipped_no_embedding = 0
    skipped_reference = 0
    skipped_no_spec = 0
    seen_paper_ids: set[str] = set()

    new_positive: list[dict] = []
    new_negative: list[dict] = []

    for rating_obj, paper_embedding in rows:
        paper_id_str = str(rating_obj.paper_id)

        # Deduplicate: keep most recent only
        if paper_id_str in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id_str)

        # Skip if no embedding
        if not paper_embedding:
            skipped_no_embedding += 1
            continue

        # Skip if already a reference paper
        if paper_id_str in reference_ids:
            skipped_reference += 1
            continue

        spec = feedback_to_anchor_spec(rating_obj.rating, rating_obj.feedback_type)
        if spec is None or spec.get("remove"):
            skipped_no_spec += 1
            continue

        # Build anchor entry. Embedding is intentionally NOT stored inline —
        # the scorer joins back to papers.embedding by paper_id at scoring time.
        # We still required paper_embedding to be present above, because we
        # don't want to create anchors that point at papers with no embedding.
        rated_at = rating_obj.rated_at
        if rated_at is None:
            rated_at = datetime.now(timezone.utc)
        entry = {
            "paper_id": paper_id_str,
            "source": "rating",
            "weight": spec["weight"],
            "added_at": rated_at.isoformat(),
            "tags": spec["tags"],
        }

        if spec["polarity"] == "positive":
            new_positive.append(entry)
        else:
            new_negative.append(entry)

    # Merge with existing anchors
    # For rating-sourced entries: replace if already exists, add if not
    def _merge(existing: list[dict], new_entries: list[dict], existing_rating_ids: set[str]) -> tuple[list[dict], int]:
        merged = list(existing)
        added = 0
        for entry in new_entries:
            pid = entry["paper_id"]
            if pid in existing_rating_ids:
                # Replace in place
                for i, a in enumerate(merged):
                    if a.get("paper_id") == pid and a.get("source") == "rating":
                        merged[i] = entry
                        break
            else:
                merged.append(entry)
                added += 1
        return merged, added

    merged_positive, added_positive = _merge(existing_positive, new_positive, existing_rating_ids_pos)
    merged_negative, added_negative = _merge(existing_negative, new_negative, existing_rating_ids_neg)

    # Enforce 100-cap per list (never evict reference entries)
    def _enforce_cap(entries: list[dict], cap: int = 100) -> list[dict]:
        if len(entries) <= cap:
            return entries
        # Separate reference and rating entries
        refs = [e for e in entries if e.get("source") == "reference"]
        ratings = [e for e in entries if e.get("source") != "reference"]
        # Sort ratings by (weight DESC, added_at DESC) and keep top N
        ratings.sort(key=lambda e: (-e.get("weight", 1.0), e.get("added_at", "")), reverse=False)
        ratings.sort(key=lambda e: (-e.get("weight", 1.0),))
        # Keep enough ratings to fill up to cap
        keep = cap - len(refs)
        if keep < 0:
            keep = 0
        # Sort by weight desc, then added_at desc for stable ordering
        ratings.sort(key=lambda e: (-e.get("weight", 1.0), e.get("added_at", "")), reverse=True)
        # Wait, we want highest weight and most recent first
        ratings.sort(key=lambda e: (e.get("weight", 1.0), e.get("added_at", "")), reverse=True)
        return refs + ratings[:keep]

    merged_positive = _enforce_cap(merged_positive)
    merged_negative = _enforce_cap(merged_negative)

    ref_count = len([a for a in merged_positive if a.get("source") == "reference"])

    summary = {
        "user_id": str(user_id),
        "email": profile.email,
        "positive_added": added_positive,
        "positive_existing_refs": ref_count,
        "negative_added": added_negative,
        "skipped_no_embedding": skipped_no_embedding,
        "skipped_reference": skipped_reference,
        "skipped_no_spec": skipped_no_spec,
    }

    if not dry_run:
        profile.positive_anchors = merged_positive
        profile.negative_anchors = merged_negative
        await session.commit()

    return summary


async def main():
    parser = argparse.ArgumentParser(description="Backfill anchor sets from historical ratings")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--user-id", type=str, help="Process only this user UUID")
    args = parser.parse_args()

    from app.database import init_db, async_session_factory
    from app.models.user_profile import UserProfile

    init_db()
    if async_session_factory is None:
        print("ERROR: Could not initialize database")
        return

    async with async_session_factory() as session:
        if args.user_id:
            user_ids = [uuid.UUID(args.user_id)]
        else:
            result = await session.execute(select(UserProfile.id))
            user_ids = [row[0] for row in result.all()]

        total_pos = 0
        total_neg = 0
        total_skipped_emb = 0
        total_skipped_ref = 0

        prefix = "[dry-run] " if args.dry_run else ""

        for uid in user_ids:
            summary = await backfill_user(session, uid, dry_run=args.dry_run)
            if "error" in summary:
                print(f"{prefix}ERROR: {summary['error']}")
                continue

            print(f"{prefix} user {summary['user_id'][:12]}... ({summary['email']})")
            print(f"            positive: +{summary['positive_added']} from ratings ({summary['positive_existing_refs']} existing from references)")
            print(f"            negative: +{summary['negative_added']} from ratings")
            print(f"            skipped: {summary['skipped_no_embedding']} ratings (no paper embedding)")
            print(f"            skipped: {summary['skipped_reference']} ratings (paper already a reference)")

            total_pos += summary["positive_added"]
            total_neg += summary["negative_added"]
            total_skipped_emb += summary["skipped_no_embedding"]
            total_skipped_ref += summary["skipped_reference"]

        print("---")
        print(f"TOTAL across {len(user_ids)} users:")
        print(f"  +{total_pos} positive anchors, +{total_neg} negative anchors added")
        print(f"  {total_skipped_emb} ratings skipped (no paper embedding)")
        print(f"  {total_skipped_ref} ratings skipped (paper already a reference)")
        if args.dry_run:
            print("Re-run without --dry-run to apply.")


if __name__ == "__main__":
    asyncio.run(main())
