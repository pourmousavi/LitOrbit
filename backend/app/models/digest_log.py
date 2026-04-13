import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class DigestLog(Base):
    """Tracks which papers were sent to which user in which digest.

    Prevents the same paper from appearing in future digests for the same user.
    """
    __tablename__ = "digest_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    paper_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    digest_type: Mapped[str] = mapped_column(String, nullable=False)  # "daily" | "weekly"
    source: Mapped[str] = mapped_column(String, nullable=False, default="email")  # "email" | "podcast"
    podcast_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("podcasts.id", ondelete="SET NULL"), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
