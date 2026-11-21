import os

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.models import Base


def test_migrations_match_models():
    """The hand-written migrations must produce exactly the schema the models describe."""
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": False})
        diff = compare_metadata(ctx, Base.metadata)
    engine.dispose()
    assert diff == [], f"Schema drift between models and migrations: {diff}"
