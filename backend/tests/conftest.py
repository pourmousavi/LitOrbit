import os
import sys
import uuid
import pytest
import pytest_asyncio

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.database import Base, get_db
from app.main import app
from app.models.paper import Paper
from app.models.journal_config import JournalConfig
from app.models.pipeline_run import PipelineRun
from app.models.paper_score import PaperScore
from app.models.user_profile import UserProfile
from app.models.rating import Rating
from app.models.podcast import Podcast
from app.models.share import Share
from app.models.digest_log import DigestLog
from app.models.digest_run import DigestRun
from app.models.scoring_signal import ScoringSignal

# Use an in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_client(db_engine):
    """Create a test client with overridden DB dependency."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
