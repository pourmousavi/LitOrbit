"""Per-(paper, user) semantic gate signals for threshold tuning."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class ScoringSignal(Base):
    __tablename__ = "scoring_signals"
    __table_args__ = (
        UniqueConstraint("paper_id", "user_id", name="uq_scoring_signal_paper_user"),
        Index("ix_scoring_signal_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    max_positive_sim: Mapped[float] = mapped_column(Float, nullable=False)
    max_negative_sim: Mapped[float] = mapped_column(Float, nullable=False)
    effective_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_used: Mapped[float] = mapped_column(Float, nullable=False)
    lambda_used: Mapped[float] = mapped_column(Float, nullable=False)
    prefilter_matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    passed_gate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    llm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_errored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
