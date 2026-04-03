import uuid
from datetime import date, datetime

from sqlalchemy import String, Text, Date, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID, StringArray


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    doi: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(StringArray(), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal: Mapped[str] = mapped_column(String, nullable=False)
    journal_source: Mapped[str] = mapped_column(String, nullable=False)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    online_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    early_access: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(StringArray(), default=list)
    categories: Mapped[list[str]] = mapped_column(StringArray(), default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
