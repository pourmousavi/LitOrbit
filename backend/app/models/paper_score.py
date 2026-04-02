import uuid
from datetime import datetime

from sqlalchemy import Float, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class PaperScore(Base):
    __tablename__ = "paper_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("paper_id", "user_id"),)
