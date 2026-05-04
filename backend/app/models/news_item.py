import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, StringArray, JSONB


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("news_sources.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    guid: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tags: Mapped[list[str]] = mapped_column(StringArray(), default=list)
    categories: Mapped[list[str]] = mapped_column(StringArray(), default=list)
    # Deferred: ~37 kB jsonb per row. See note on Paper.embedding.
    embedding: Mapped[dict | None] = mapped_column(JSONB(), nullable=True, deferred=True)
    relevance_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    primary_cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("news_clusters.id", ondelete="SET NULL"), nullable=True)
    is_cluster_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    llm_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    llm_score_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scholarlib_ref_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ingest_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("news_ingest_runs.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
