from datetime import datetime

from sqlalchemy import Integer, Boolean, DateTime, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JSONB


class SystemSettings(Base):
    __tablename__ = "system_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    max_podcasts_per_user_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    digest_podcast_enabled_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_papers_per_digest: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    platform_keywords: Mapped[list] = mapped_column(JSONB(), nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
