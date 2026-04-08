import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID


class PaperFavorite(Base):
    __tablename__ = "paper_favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    favorited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
