import uuid
from datetime import datetime

from sqlalchemy import Text, DateTime, CheckConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, JSONB


class UserInteraction(Base):
    __tablename__ = "user_interactions"
    __table_args__ = (
        CheckConstraint("content_type IN ('paper','news')", name="user_interactions_content_type_check"),
        CheckConstraint(
            "event_type IN ('viewed','rated','starred','marked_read',"
            "'sent_to_scholarlib','included_in_digest','listened')",
            name="user_interactions_event_type_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_value: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
