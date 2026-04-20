"""Resumable corpus re-embedding sweep for task_type=SEMANTIC_SIMILARITY.

Usage:
    cd backend
    python -m scripts.reembed_corpus --dry-run        # preview counts only
    python -m scripts.reembed_corpus                   # full sweep
    python -m scripts.reembed_corpus --limit 100       # embed at most 100 papers this run
    python -m scripts.reembed_corpus --skip-anchors    # re-embed papers only; skip anchor refresh
    python -m scripts.reembed_corpus --anchors-only    # skip paper re-embed; only refresh anchors

Resumable: rows with embedding_task_type != 'SEMANTIC_SIMILARITY' are pending.
Killing and re-running continues from where it left off.
"""

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.orm.attributes import flag_modified

from app.services.ranking.embedder import (
    embed_text,
    prepare_paper_text,
    get_quota_status,
    EmbeddingQuotaExhausted,
    EmbeddingAPIError,
    EMBEDDING_TASK_TYPE,
)


async def _count_pending(session, model_cls):
    """Count rows with embedding but not yet re-embedded."""
    from sqlalchemy import or_
    result = await session.execute(
        select(func.count()).where(
            model_cls.embedding.isnot(None),
            or_(
                model_cls.embedding_task_type.is_(None),
                model_cls.embedding_task_type != EMBEDDING_TASK_TYPE,
            ),
        )
    )
    return result.scalar() or 0


async def _count_done(session, model_cls):
    """Count rows already re-embedded."""
    result = await session.execute(
        select(func.count()).where(
            model_cls.embedding.isnot(None),
            model_cls.embedding_task_type == EMBEDDING_TASK_TYPE,
        )
    )
    return result.scalar() or 0


async def dry_run(session):
    """Print counts and estimates without modifying anything."""
    from app.models.paper import Paper
    from app.models.reference_paper import ReferencePaper
    from app.models.user_profile import UserProfile

    papers_pending = await _count_pending(session, Paper)
    papers_done = await _count_done(session, Paper)
    refs_pending = await _count_pending(session, ReferencePaper)

    total_api_calls = papers_pending + refs_pending
    quota = get_quota_status()
    remaining = quota["daily_remaining"]

    days = max(1, (total_api_calls + 949) // 950) if total_api_calls > 0 else 0

    print("[dry-run] Phase A (papers + reference_papers re-embed):")
    print(f"  papers to re-embed:             {papers_pending} ({papers_done} already done, {papers_pending} pending)")
    print(f"  reference_papers to re-embed:   {refs_pending}")
    print(f"  estimated API calls:            {total_api_calls}")
    print(f"  estimated wall time:            ~{days} day{'s' if days != 1 else ''} at 950/day free tier")
    print(f"  today's remaining quota:        {remaining}")

    # Phase B stats
    result = await session.execute(select(UserProfile))
    users = result.scalars().all()
    users_with_anchors = 0
    total_anchors = 0
    anchors_swept = 0
    anchors_pending_refresh = 0

    for u in users:
        all_anchors = list(u.positive_anchors or []) + list(u.negative_anchors or [])
        if not all_anchors:
            continue
        users_with_anchors += 1
        total_anchors += len(all_anchors)

        paper_ids = [a["paper_id"] for a in all_anchors if a.get("paper_id")]
        if paper_ids:
            from app.models.paper import Paper as P
            swept_result = await session.execute(
                select(func.count()).where(
                    P.id.in_([uuid.UUID(pid) for pid in paper_ids]),
                    P.embedding_task_type == EMBEDDING_TASK_TYPE,
                )
            )
            swept = swept_result.scalar() or 0
            anchors_swept += swept
            anchors_pending_refresh += len(paper_ids) - swept

    print()
    print("[dry-run] Phase B (anchor snapshot refresh):")
    print(f"  users with anchors:             {users_with_anchors}")
    print(f"  total anchors across all users: {total_anchors}")
    print(f"  anchors whose paper is already swept: {anchors_swept}")
    print(f"  anchors whose paper is pending:  {anchors_pending_refresh}")
    print()
    print("Run without --dry-run to start Phase A.")
    print("Phase B will be meaningful once Phase A is substantially complete.")


async def phase_a(session, limit: int | None = None):
    """Re-embed papers and reference_papers with new task_type."""
    from app.models.paper import Paper
    from app.models.reference_paper import ReferencePaper
    from sqlalchemy import or_

    # Papers first
    total_pending = await _count_pending(session, Paper)
    if total_pending == 0:
        print("[sweep] All papers already re-embedded.")
    else:
        print(f"[sweep] Starting Phase A (papers + reference_papers)")
        result = await session.execute(
            select(Paper)
            .where(
                Paper.embedding.isnot(None),
                or_(
                    Paper.embedding_task_type.is_(None),
                    Paper.embedding_task_type != EMBEDDING_TASK_TYPE,
                ),
            )
            .order_by(Paper.id)
        )
        papers = result.scalars().all()

        processed = 0
        effective_limit = limit if limit is not None else len(papers)

        for i, paper in enumerate(papers):
            if processed >= effective_limit:
                break

            text = prepare_paper_text(paper.title, paper.abstract or "")
            try:
                embedding = await embed_text(text)
            except EmbeddingAPIError as e:
                print(f"[sweep] API error: {e}. Committing progress and exiting.")
                await session.commit()
                sys.exit(1)

            if embedding is None:
                # Quota exhausted
                await session.commit()
                remaining = total_pending - processed
                print(f"[sweep] Quota exhausted. {processed} papers re-embedded today. {remaining} remaining for tomorrow.")
                print("[sweep] Phase A exiting cleanly. Re-run tomorrow to continue.")
                return False  # signal: not complete

            paper.embedding = embedding
            paper.embedding_task_type = EMBEDDING_TASK_TYPE
            processed += 1

            if processed % 10 == 0:
                await session.commit()
                quota = get_quota_status()
                print(f"[sweep] {processed}/{total_pending} papers re-embedded (quota: {quota['daily_used']}/{quota['daily_limit']} used today)")

        await session.commit()

        if processed >= total_pending:
            print(f"[sweep] All {total_pending} papers re-embedded.")
        elif limit is not None and processed >= limit:
            remaining = total_pending - processed
            print(f"[sweep] Limit reached. {processed} papers re-embedded this run. {remaining} remaining.")

    # Reference papers
    refs_pending = await _count_pending(session, ReferencePaper)
    if refs_pending == 0:
        refs_done = await _count_done(session, ReferencePaper)
        if refs_done > 0:
            print(f"[sweep] All {refs_done} reference_papers already re-embedded.")
    else:
        result = await session.execute(
            select(ReferencePaper)
            .where(
                ReferencePaper.embedding.isnot(None),
                or_(
                    ReferencePaper.embedding_task_type.is_(None),
                    ReferencePaper.embedding_task_type != EMBEDDING_TASK_TYPE,
                ),
            )
            .order_by(ReferencePaper.id)
        )
        refs = result.scalars().all()

        ref_processed = 0
        for ref in refs:
            text = prepare_paper_text(ref.title, ref.abstract or "")
            try:
                embedding = await embed_text(text)
            except EmbeddingAPIError as e:
                print(f"[sweep] API error on reference paper: {e}. Committing and exiting.")
                await session.commit()
                sys.exit(1)

            if embedding is None:
                await session.commit()
                print(f"[sweep] Quota exhausted during reference papers. {ref_processed} done, {refs_pending - ref_processed} remaining.")
                return False

            ref.embedding = embedding
            ref.embedding_task_type = EMBEDDING_TASK_TYPE
            ref_processed += 1

        await session.commit()
        print(f"[sweep] {ref_processed} reference_papers re-embedded.")

    # Check if everything is done
    papers_still = await _count_pending(session, Paper)
    refs_still = await _count_pending(session, ReferencePaper)
    papers_done = await _count_done(session, Paper)
    refs_done = await _count_done(session, ReferencePaper)

    if papers_still == 0 and refs_still == 0:
        print(f"[sweep] Phase A complete. All {papers_done} papers and {refs_done} reference_papers re-embedded.")
        return True
    return False


async def phase_b(session):
    """Refresh anchor snapshots from re-embedded papers."""
    from app.models.user_profile import UserProfile
    from app.models.paper import Paper

    print("[sweep] Starting Phase B (anchor refresh)...")

    result = await session.execute(select(UserProfile))
    users = result.scalars().all()

    total_refreshed = 0
    total_skipped = 0

    for user in users:
        pos_anchors = list(user.positive_anchors or [])
        neg_anchors = list(user.negative_anchors or [])
        all_anchors = pos_anchors + neg_anchors

        if not all_anchors:
            continue

        # Collect paper_ids referenced by anchors
        paper_ids = set()
        for a in all_anchors:
            pid = a.get("paper_id")
            if pid:
                paper_ids.add(pid)

        if not paper_ids:
            continue

        # Fetch current embeddings for swept papers
        paper_result = await session.execute(
            select(Paper.id, Paper.embedding).where(
                Paper.id.in_([uuid.UUID(pid) for pid in paper_ids]),
                Paper.embedding_task_type == EMBEDDING_TASK_TYPE,
            )
        )
        embedding_map = {str(row[0]): row[1] for row in paper_result.all()}

        # Also check reference_papers
        from app.models.reference_paper import ReferencePaper
        ref_result = await session.execute(
            select(ReferencePaper.id, ReferencePaper.embedding).where(
                ReferencePaper.id.in_([uuid.UUID(pid) for pid in paper_ids]),
                ReferencePaper.embedding_task_type == EMBEDDING_TASK_TYPE,
            )
        )
        for row in ref_result.all():
            embedding_map.setdefault(str(row[0]), row[1])

        user_refreshed = 0
        user_skipped = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        def _refresh_list(anchors):
            nonlocal user_refreshed, user_skipped
            changed = False
            for anchor in anchors:
                pid = anchor.get("paper_id")
                if pid and pid in embedding_map:
                    anchor["embedding"] = embedding_map[pid]
                    anchor["refreshed_at"] = now_iso
                    user_refreshed += 1
                    changed = True
                elif pid:
                    user_skipped += 1
            return changed

        pos_changed = _refresh_list(pos_anchors)
        neg_changed = _refresh_list(neg_anchors)

        if pos_changed:
            user.positive_anchors = pos_anchors
            flag_modified(user, "positive_anchors")
        if neg_changed:
            user.negative_anchors = neg_anchors
            flag_modified(user, "negative_anchors")

        pos_refreshed = sum(1 for a in pos_anchors if a.get("refreshed_at") == now_iso)
        neg_refreshed = sum(1 for a in neg_anchors if a.get("refreshed_at") == now_iso)
        pos_total = len(pos_anchors)
        neg_total = len(neg_anchors)

        print(f"[sweep] User {str(user.id)[:8]}...: refreshed {pos_refreshed}/{pos_total} positive anchors, {neg_refreshed}/{neg_total} negative anchors")

        total_refreshed += user_refreshed
        total_skipped += user_skipped

    await session.commit()
    print(f"[sweep] Phase B complete. {total_refreshed} anchor snapshots refreshed, {total_skipped} skipped.")


async def main():
    parser = argparse.ArgumentParser(description="Re-embed corpus with task_type=SEMANTIC_SIMILARITY")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts only, no DB writes")
    parser.add_argument("--limit", type=int, default=None, help="Max papers to re-embed this run")
    parser.add_argument("--skip-anchors", action="store_true", help="Skip Phase B (anchor refresh)")
    parser.add_argument("--anchors-only", action="store_true", help="Skip Phase A; only refresh anchors")
    args = parser.parse_args()

    from app.database import init_db
    from app import database as _db
    # Import all models so SQLAlchemy can resolve FK references during flush
    import app.models.user_profile  # noqa: F401
    import app.models.paper  # noqa: F401
    import app.models.reference_paper  # noqa: F401

    init_db()
    if _db.async_session_factory is None:
        print("ERROR: Could not initialize database")
        sys.exit(1)

    async with _db.async_session_factory() as session:
        if args.dry_run:
            await dry_run(session)
            return

        if args.anchors_only:
            await phase_b(session)
            return

        phase_a_complete = await phase_a(session, limit=args.limit)

        if not args.skip_anchors and phase_a_complete:
            await phase_b(session)
        elif args.skip_anchors:
            print("[sweep] --skip-anchors: skipping Phase B.")
        else:
            print("[sweep] Phase A not yet complete. Phase B deferred to next full run.")


if __name__ == "__main__":
    asyncio.run(main())
