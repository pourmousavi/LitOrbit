"""Custom SQLAlchemy types that work with both PostgreSQL and SQLite."""
import json
import uuid

from sqlalchemy import TypeDecorator, Text, String
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY, UUID as PG_UUID, JSONB as PG_JSONB


class StringArray(TypeDecorator):
    """Stores a list of strings. Uses ARRAY on Postgres, JSON text on SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(String))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return "[]"
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value or []
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return json.loads(value)


class JSONB(TypeDecorator):
    """Stores JSON. Uses JSONB on Postgres, JSON text on SQLite.

    IMPORTANT: On PostgreSQL, PG_JSONB encodes Python None as the JSONB
    literal ``null`` (NOT SQL NULL). We use Text as the impl and serialize
    to JSON ourselves so that Python None → SQL NULL.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            # Use Text, not PG_JSONB, so Python None stays as SQL NULL
            # instead of being encoded as JSONB literal null.
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)


class UUID(TypeDecorator):
    """Stores UUID. Uses native UUID on Postgres, String on SQLite."""
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
