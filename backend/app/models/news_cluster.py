import uuid
from datetime import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, JSONB


class NewsCluster(Base):
    __tablename__ = "news_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    primary_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("news_items.id", ondelete="SET NULL"), nullable=True)
    centroid_embedding: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
