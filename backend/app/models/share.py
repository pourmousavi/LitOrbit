import uuid
from datetime import datetime

from sqlalchemy import Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("papers.id", ondelete="CASCADE"), nullable=True)
    shared_by: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id"), nullable=False)
    shared_with: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("user_profiles.id"), nullable=False)
    annotation: Mapped[str | None] = mapped_column(Text, nullable=True)
    podcast_id: Mapped[uuid.UUID | None] = mapped_column(UUID(), ForeignKey("podcasts.id"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
