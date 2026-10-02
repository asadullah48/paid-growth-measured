"""Public-demo support: a read-only switch and a one-time database bootstrap.

Both are OFF unless their environment variables are set, so local development
and the test suite behave exactly as before.

DEMO_READ_ONLY=true
    Every write is refused with 403 except signing in and out. A public demo
    publishes its password; without this, any visitor could put text into a
    workspace that the next visitor sees under the maintainer's name.

DEMO_BOOTSTRAP=true
    On the first request an instance serves, run `alembic upgrade head` and the
    idempotent synthetic seed. Serverless hosts have no release step to run
    them in. On PostgreSQL an advisory lock serialises concurrent cold starts.
"""
import logging
import os
import threading
from pathlib import Path

from sqlalchemy import text

log = logging.getLogger(__name__)

# Writes a read-only demo still needs: a session is a row in the database.
ALWAYS_ALLOWED = frozenset({'/auth/login', '/auth/logout'})
WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})
READ_ONLY_MESSAGE = 'This public demo is read-only. Run the project locally to create and edit records.'
_LOCK_KEY = 7_340_211  # arbitrary, fixed: identifies this app's bootstrap lock

_bootstrapped = False
_guard = threading.Lock()


def _flag(name: str) -> bool:
    return os.getenv(name, 'false').strip().lower() == 'true'


def read_only() -> bool:
    return _flag('DEMO_READ_ONLY')


def blocks(method: str, path: str) -> bool:
    """True when read-only mode must refuse this request."""
    return read_only() and method.upper() in WRITE_METHODS and path not in ALWAYS_ALLOWED


def ensure_bootstrapped() -> None:
    """Run migrations and the seed once per process, if DEMO_BOOTSTRAP is on."""
    global _bootstrapped
    if _bootstrapped or not _flag('DEMO_BOOTSTRAP'):
        return
    with _guard:
        if _bootstrapped:
            return
        from alembic import command
        from alembic.config import Config

        from .database import engine
        from .seed import seed

        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / 'alembic.ini'))
        config.set_main_option('script_location', str(root / 'migrations'))
        postgres = engine.dialect.name == 'postgresql'
        with engine.connect() as lock:
            if postgres:
                lock.execute(text('SELECT pg_advisory_lock(:k)'), {'k': _LOCK_KEY})
            try:
                command.upgrade(config, 'head')
                seed()
            finally:
                if postgres:
                    lock.execute(text('SELECT pg_advisory_unlock(:k)'), {'k': _LOCK_KEY})
        _bootstrapped = True
        log.info('Demo database bootstrapped.')
