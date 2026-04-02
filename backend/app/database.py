from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    settings = get_settings()
    if settings.database_url:
        url = settings.database_url
    elif settings.supabase_url:
        # Derive Postgres connection from Supabase URL
        # Supabase URL format: https://<project>.supabase.co
        project_ref = settings.supabase_url.replace("https://", "").split(".")[0]
        url = f"postgresql+asyncpg://postgres.{project_ref}:postgres@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
    else:
        # Fallback for testing with SQLite
        url = "sqlite+aiosqlite:///./test.db"
    return create_async_engine(url, echo=settings.environment == "development")


engine = None
async_session_factory = None


def init_db():
    global engine, async_session_factory
    engine = get_engine()
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    if async_session_factory is None:
        init_db()
    async with async_session_factory() as session:
        yield session
