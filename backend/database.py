import logging
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import settings, BACKEND_DIR

logger = logging.getLogger("relaydesk.db")

SQLITE_DB_PATH = os.path.join(BACKEND_DIR, "relaydesk.db")


def _resolve_database_url() -> str:
    if not settings.DATABASE_URL:
        return (
            f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
            f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            "?charset=utf8mb4"
        )
    url = settings.DATABASE_URL
    # Relative SQLite paths ("sqlite:///./relaydesk.db") used to depend on the
    # current working directory, which silently created a second database when
    # the server was started from the repo root. Anchor them to backend/.
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////") and url != "sqlite:///:memory:":
        path = url[len(prefix):]
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(BACKEND_DIR, path))
            url = prefix + path.replace(os.sep, "/")
    return url


DATABASE_URL = _resolve_database_url()


def create_db_engine():
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    eng = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with eng.connect():
            pass
        return eng
    except Exception as e:
        # Never silently swap databases in production — that would split data.
        if settings.is_production:
            raise
        logger.warning("Could not connect to MySQL (%s). Falling back to SQLite: %s", e, SQLITE_DB_PATH)
        sqlite_url = f"sqlite:///{SQLITE_DB_PATH.replace(os.sep, '/')}"
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})


engine = create_db_engine()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ── Schema migrations (Alembic) ───────────────────────────────────
BASELINE_REVISION = "0001"

# Columns that older, pre-Alembic versions of the app added at runtime.
_LEGACY_COLUMNS = {
    "users": {"support_level": "VARCHAR(16) DEFAULT 'L1'", "primary_device": "JSON"},
    "tickets": {
        "target_level": "VARCHAR(16) DEFAULT 'L1'", "attachments": "JSON",
        "device_name": "VARCHAR(128)", "device_os": "VARCHAR(128)", "ip_address": "VARCHAR(64)",
        "subnet_vlan": "VARCHAR(128)", "mac_address": "VARCHAR(64)", "asset_tag": "VARCHAR(64)",
        "serial_number": "VARCHAR(64)", "last_reboot": "VARCHAR(128)", "edr_status": "VARCHAR(128)",
        "hardware_specs": "VARCHAR(256)", "domain_join": "VARCHAR(128)", "office_location": "VARCHAR(128)",
    },
    "ticket_messages": {"attachments": "JSON"},
}


def _bring_legacy_db_to_baseline(connection) -> None:
    """A database created before Alembic was introduced may be missing tables
    or columns that the baseline revision assumes. Fill those gaps so it can
    be stamped at the baseline and upgraded normally from there."""
    import models  # noqa: F401  (registers tables)

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _LEGACY_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in present:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    missing = [t for name, t in Base.metadata.tables.items() if name not in existing_tables]
    if missing:
        Base.metadata.create_all(bind=connection, tables=missing)


def run_migrations() -> None:
    """Upgrade the database to the latest Alembic revision."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))

    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and "users" in tables:
            logger.info("Adopting pre-Alembic database at revision %s", BASELINE_REVISION)
            _bring_legacy_db_to_baseline(connection)
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
