import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class Podcast(Base):
    __tablename__ = "podcasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("papers.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("user_profiles.id"), nullable=True)
    voice_mode: Mapped[str] = mapped_column(String, nullable=False, default="single")
    podcast_type: Mapped[str] = mapped_column(String, nullable=False, default="paper")  # "paper" | "digest"
    title: Mapped[str | None] = mapped_column(Text, nullable=True)  # display title for digest podcasts
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    listen_count: Mapped[int] = mapped_column(Integer, default=0)
    last_listened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
