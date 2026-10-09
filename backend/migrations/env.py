"""Alembic environment — reuses the application's engine and models."""

import os
import sys

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base  # noqa: E402
import models  # noqa: E402,F401  (registers every table on Base.metadata)

target_metadata = Base.metadata


def _configure(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite cannot ALTER most things in place; batch mode rebuilds the table
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline():
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # The app passes its own connection when migrating at startup
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        return
    with engine.connect() as connection:
        _configure(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
