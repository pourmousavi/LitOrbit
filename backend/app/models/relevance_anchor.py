import uuid
from datetime import datetime

from sqlalchemy import Text, Numeric, Boolean, DateTime, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, JSONB


class RelevanceAnchor(Base):
    __tablename__ = "relevance_anchors"
    __table_args__ = (
        CheckConstraint("source_content_type IN ('paper','news')", name="relevance_anchors_type_check"),
        CheckConstraint("weight BETWEEN 0 AND 3", name="relevance_anchors_weight_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    source_content_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_content_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric, nullable=False, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
