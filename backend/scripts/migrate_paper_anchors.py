"""Migrate existing paper anchors from user_profiles.positive_anchors
into the new relevance_anchors table.

Reads reference-sourced anchors from each user's positive_anchors JSONB array,
deduplicates by paper_id, and inserts into relevance_anchors with
source_content_type='paper'.

Usage:
    cd backend
    python -m scripts.migrate_paper_anchors --dry-run   # preview
    python -m scripts.migrate_paper_anchors              # apply

Idempotent: skips anchors whose source_content_id already exists in the table.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.models.relevance_anchor import RelevanceAnchor


async def migrate_anchors(dry_run: bool = True) -> None:
    from app.database import init_db
    from app import database as _db
    from app.models.user_profile import UserProfile
    from app.models.paper import Paper

    init_db()
    if _db.async_session_factory is None:
        print("ERROR: Could not initialize database")
        return

    async with _db.async_session_factory() as session:
        # Get all user profiles
        result = await session.execute(select(UserProfile))
        profiles = result.scalars().all()

        seen_paper_ids: set[str] = set()
        anchors_to_add: list[dict] = []

        for profile in profiles:
            positive_anchors = profile.positive_anchors or []
            for anchor in positive_anchors:
                paper_id = anchor.get("paper_id")
                embedding = anchor.get("embedding")
                source = anchor.get("source", "unknown")

                if not paper_id or not embedding:
                    continue

                # Only migrate reference-sourced anchors (or all if few exist)
                # Deduplicate across users
                if paper_id in seen_paper_ids:
                    continue
                seen_paper_ids.add(paper_id)

                # Look up paper title for label
                paper = await session.get(Paper, uuid.UUID(paper_id))
                if paper:
                    label = paper.title[:200]
                else:
                    label = f"Paper anchor {paper_id[:8]}"

                # Check if already migrated
                existing = await session.execute(
                    select(RelevanceAnchor.id).where(
                        RelevanceAnchor.source_content_type == "paper",
                        RelevanceAnchor.source_content_id == uuid.UUID(paper_id),
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    print(f"  SKIP (already exists): {label[:60]}")
                    continue

                anchors_to_add.append({
                    "source_content_type": "paper",
                    "source_content_id": uuid.UUID(paper_id),
                    "label": label,
                    "notes": f"Migrated from user {profile.email}, source={source}",
                    "embedding": embedding,
                    "weight": float(anchor.get("weight", 1.0)),
                    "enabled": True,
                })

        prefix = "[dry-run] " if dry_run else ""
        print(f"\n{prefix}Found {len(anchors_to_add)} unique paper anchors to migrate")

        for a in anchors_to_add:
            print(f"  {prefix}+ {a['label'][:60]}... (weight={a['weight']:.2f})")

        if not dry_run and anchors_to_add:
            for a in anchors_to_add:
                session.add(RelevanceAnchor(**a))
            await session.commit()
            print(f"\nMigrated {len(anchors_to_add)} anchors into relevance_anchors table.")
        elif dry_run:
            print(f"\nRe-run without --dry-run to apply.")
        else:
            print("\nNo anchors to migrate.")


def main():
    parser = argparse.ArgumentParser(description="Migrate paper anchors to relevance_anchors table")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()
    asyncio.run(migrate_anchors(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
