import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, StringArray, JSONB


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="researcher")
    email: Mapped[str] = mapped_column(Text, nullable=False)
    interest_keywords: Mapped[list[str]] = mapped_column(StringArray(), default=list)
    interest_categories: Mapped[list[str]] = mapped_column(StringArray(), default=list)
    # Embedding centroid of reference papers — used by the pipeline pre-filter.
    # Stored as a JSON list under the hood; values are floats indexed by position.
    interest_vector: Mapped[dict] = mapped_column(JSONB(), default=dict)
    # Human-readable {category_name: weight in [-1, 1]} learned from user ratings.
    # Powers the Interest Profile chart in the UI.
    category_weights: Mapped[dict] = mapped_column(JSONB(), default=dict)
    podcast_preference: Mapped[str] = mapped_column(String, default="single")
    email_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_frequency: Mapped[str] = mapped_column(String, default="weekly")
    digest_day: Mapped[str] = mapped_column(String, default="monday")  # day of week for weekly digests
    digest_podcast_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_podcast_voice_mode: Mapped[str] = mapped_column(String, default="dual")
    digest_top_papers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Standalone podcast digest (independent schedule from email digest)
    podcast_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    podcast_digest_frequency: Mapped[str] = mapped_column(String, default="weekly")
    podcast_digest_day: Mapped[str] = mapped_column(String, default="monday")
    podcast_digest_top_papers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    podcast_digest_voice_mode: Mapped[str] = mapped_column(String, default="dual")
    scoring_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    single_voice_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    dual_voice_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    single_voice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    dual_voice_alex_id: Mapped[str | None] = mapped_column(String, nullable=True)
    dual_voice_sam_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Podcast RSS feed settings
    podcast_feed_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    podcast_feed_token: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    podcast_feed_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    podcast_feed_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    podcast_feed_author: Mapped[str | None] = mapped_column(String, nullable=True)
    podcast_feed_cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Activity tracking
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
