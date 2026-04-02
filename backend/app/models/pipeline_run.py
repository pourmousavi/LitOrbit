import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, JSONB


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    papers_discovered: Mapped[int] = mapped_column(Integer, default=0)
    papers_filtered: Mapped[int] = mapped_column(Integer, default=0)
    papers_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_log: Mapped[list] = mapped_column(JSONB(), default=list)
