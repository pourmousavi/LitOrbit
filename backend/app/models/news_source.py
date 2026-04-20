import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, Integer, Numeric, DateTime, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class NewsSource(Base):
    __tablename__ = "news_sources"
    __table_args__ = (
        CheckConstraint("authority_weight BETWEEN 0 AND 2", name="news_sources_authority_weight_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False)
    website_url: Mapped[str] = mapped_column(Text, nullable=False)
    authority_weight: Mapped[float] = mapped_column(Numeric, nullable=False, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    per_source_daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    per_source_min_relevance: Mapped[float] = mapped_column(Numeric, nullable=False, default=0.30)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fetch_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
