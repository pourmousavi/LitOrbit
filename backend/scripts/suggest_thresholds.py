"""Threshold suggestion script from rated scoring signals.

Usage:
    cd backend
    python -m scripts.suggest_thresholds                    # report for all users combined
    python -m scripts.suggest_thresholds --user-id <uuid>   # per-user
    python -m scripts.suggest_thresholds --min-rated 50     # require at least N rated signals (default 30)
"""

import argparse
import asyncio
import math
import sys
import uuid

from sqlalchemy import select


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _best_threshold_f1(positives: list[float], negatives: list[float]) -> tuple[float, float]:
    """Find threshold that maximises F1 on effective_score predicting rating >= 7.

    Returns (best_threshold, best_f1).
    """
    best_t = 0.5
    best_f1 = 0.0
    for t_int in range(0, 101):
        t = t_int / 100.0
        tp = sum(1 for v in positives if v >= t)
        fp = sum(1 for v in negatives if v >= t)
        fn = sum(1 for v in positives if v < t)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
    return (best_t, best_f1)


def _best_lambda_f1(
    pos_data: list[tuple[float, float]],
    neg_data: list[tuple[float, float]],
    threshold: float,
) -> tuple[float, float]:
    """Find lambda that maximises F1 at the given threshold.

    pos_data/neg_data are lists of (max_positive_sim, max_negative_sim).
    Returns (best_lambda, best_f1).
    """
    best_lam = 0.5
    best_f1 = 0.0
    for lam_int in range(0, 201):
        lam = lam_int / 100.0
        tp = sum(1 for p, n in pos_data if (p - lam * n) >= threshold)
        fp = sum(1 for p, n in neg_data if (p - lam * n) >= threshold)
        fn = sum(1 for p, n in pos_data if (p - lam * n) < threshold)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        if f1 > best_f1:
            best_f1 = f1
            best_lam = lam
    return (best_lam, best_f1)


async def run_report(
    session,
    user_id: uuid.UUID | None = None,
    min_rated: int = 30,
) -> str:
    """Generate threshold suggestion report. Returns the report text."""
    from app.models.scoring_signal import ScoringSignal
    from app.models.rating import Rating
    from app.models.system_settings import SystemSettings

    # Join signals with ratings
    query = (
        select(
            ScoringSignal.max_positive_sim,
            ScoringSignal.max_negative_sim,
            ScoringSignal.effective_score,
            Rating.rating,
        )
        .join(Rating, (Rating.paper_id == ScoringSignal.paper_id) & (Rating.user_id == ScoringSignal.user_id))
    )
    if user_id:
        query = query.where(ScoringSignal.user_id == user_id)

    result = await session.execute(query)
    rows = result.all()

    if len(rows) < min_rated:
        return (
            f"Not enough rated signals yet ({len(rows)} found, need {min_rated}). "
            f"Come back in a week or two."
        )

    # Label
    positives = [(r.max_positive_sim, r.max_negative_sim, r.effective_score) for r in rows if r.rating >= 7]
    negatives = [(r.max_positive_sim, r.max_negative_sim, r.effective_score) for r in rows if r.rating <= 3]
    middle = [r for r in rows if 4 <= r.rating <= 6]

    # Current config
    settings = (await session.execute(select(SystemSettings).where(SystemSettings.id == 1))).scalar_one_or_none()
    current_threshold = settings.similarity_threshold if settings else 0.50
    current_lambda = settings.negative_anchor_lambda if settings else 0.5

    # Distributions
    pos_max_pos = [p[0] for p in positives]
    neg_max_pos = [n[0] for n in negatives]
    pos_max_neg = [p[1] for p in positives]
    neg_max_neg = [n[1] for n in negatives]
    pos_eff = [p[2] for p in positives]
    neg_eff = [n[2] for n in negatives]

    # Best threshold
    suggested_t, suggested_f1 = _best_threshold_f1(pos_eff, neg_eff)
    _, current_f1 = _best_threshold_f1(pos_eff, neg_eff)  # F1 at current threshold
    # Actually compute F1 at current threshold specifically
    tp = sum(1 for v in pos_eff if v >= current_threshold)
    fp = sum(1 for v in neg_eff if v >= current_threshold)
    fn = sum(1 for v in pos_eff if v < current_threshold)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    current_f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    # Best lambda
    pos_pn = [(p[0], p[1]) for p in positives]
    neg_pn = [(n[0], n[1]) for n in negatives]
    suggested_lam, lam_f1 = _best_lambda_f1(pos_pn, neg_pn, current_threshold)

    lines = [
        "Threshold suggestion report",
        "===========================",
        f"Based on {len(rows)} rated (paper, user) signals:",
        f"  Positives (rating >= 7):  {len(positives)}",
        f"  Negatives (rating <= 3):  {len(negatives)}",
        f"  Middle (4-6), skipped:    {len(middle)}",
        "",
        "Current config:",
        f"  similarity_threshold: {current_threshold}",
        f"  negative_anchor_lambda: {current_lambda}",
        "",
        "Signal distributions:",
        "  max_positive_sim:",
        f"    positives: mean={_mean(pos_max_pos):.2f}, std={_std(pos_max_pos):.2f}" if pos_max_pos else "    positives: (none)",
        f"    negatives: mean={_mean(neg_max_pos):.2f}, std={_std(neg_max_pos):.2f}" if neg_max_pos else "    negatives: (none)",
        "  max_negative_sim:",
        f"    positives: mean={_mean(pos_max_neg):.2f}, std={_std(pos_max_neg):.2f}" if pos_max_neg else "    positives: (none)",
        f"    negatives: mean={_mean(neg_max_neg):.2f}, std={_std(neg_max_neg):.2f}" if neg_max_neg else "    negatives: (none)",
        "  effective_score:",
        f"    positives: mean={_mean(pos_eff):.2f}, std={_std(pos_eff):.2f}" if pos_eff else "    positives: (none)",
        f"    negatives: mean={_mean(neg_eff):.2f}, std={_std(neg_eff):.2f}" if neg_eff else "    negatives: (none)",
        "",
        "Suggested thresholds:",
        f"  similarity_threshold: {suggested_t:.2f}  (F1={suggested_f1:.2f}, vs F1={current_f1:.2f} at current {current_threshold})",
        f"  negative_anchor_lambda: {suggested_lam:.1f} (marginal gain; current {current_lambda} is fine)" if abs(suggested_lam - current_lambda) < 0.2 else f"  negative_anchor_lambda: {suggested_lam:.1f} (F1={lam_f1:.2f})",
        "",
        "To apply, PUT /api/v1/admin/thresholds with:",
        f'  {{"similarity_threshold": {suggested_t:.2f}, "negative_anchor_lambda": {current_lambda}}}',
        "",
    ]

    if abs(suggested_t - current_threshold) < 0.05:
        lines.append("Or leave as-is — the current threshold is close enough to optimal.")
    else:
        lines.append(f"Consider updating — the suggested threshold differs by {abs(suggested_t - current_threshold):.2f} from current.")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Suggest optimal threshold and lambda from rated scoring signals")
    parser.add_argument("--user-id", type=str, default=None, help="Filter to a specific user UUID")
    parser.add_argument("--min-rated", type=int, default=30, help="Minimum rated signals required (default 30)")
    args = parser.parse_args()

    from app.database import init_db
    from app import database as _db

    init_db()
    if _db.async_session_factory is None:
        print("ERROR: Could not initialize database")
        sys.exit(1)

    uid = uuid.UUID(args.user_id) if args.user_id else None

    async with _db.async_session_factory() as session:
        report = await run_report(session, user_id=uid, min_rated=args.min_rated)
        print(report)


if __name__ == "__main__":
    asyncio.run(main())
