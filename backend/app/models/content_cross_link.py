import uuid
from datetime import datetime

from sqlalchemy import Text, Numeric, DateTime, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class ContentCrossLink(Base):
    __tablename__ = "content_cross_links"
    __table_args__ = (
        CheckConstraint("source_content_type IN ('paper','news')", name="cross_links_source_type_check"),
        CheckConstraint("target_content_type IN ('paper','news')", name="cross_links_target_type_check"),
        CheckConstraint(
            "NOT (source_content_type = target_content_type AND source_content_id = target_content_id)",
            name="no_self_link",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    source_content_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_content_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    target_content_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_content_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    similarity: Mapped[float] = mapped_column(Numeric, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
