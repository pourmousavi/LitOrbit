import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_type: Mapped[str | None] = mapped_column(String, nullable=True)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("paper_id", "user_id"),
        CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
    )
