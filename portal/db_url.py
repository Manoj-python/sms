"""Tiny DATABASE_URL -> Django DATABASES['default'] parser.

Supports the same two schemes the FastAPI portal's .env used:
sqlite:///absolute/path.db and mysql+pymysql://user:pass@host:port/dbname.
Avoids adding a dj-database-url dependency for something this small.
"""

from urllib.parse import urlsplit


def parse_database_url(url: str, base_dir) -> dict:
    parts = urlsplit(url)
    scheme = parts.scheme.split("+")[0]

    if scheme == "sqlite":
        # sqlite:///relative/path.db or sqlite:///C:/abs/path.db (Windows) —
        # urlsplit always leaves exactly one leading "/" in .path for these
        # (the rest of the "///" is consumed as the empty netloc marker), so
        # stripping one leading slash recovers "relative.db" or
        # "C:/abs/path.db" in both cases.
        path = parts.path
        if path.startswith("/"):
            path = path[1:]
        if not path:
            path = "portal_dev.db"
        # Resolve relative paths against base_dir rather than leaving them
        # relative to the process's CWD — different launchers (manage.py run
        # directly vs. a dev-server wrapper) can start the process from
        # different working directories, silently pointing at two different
        # sqlite files otherwise.
        from pathlib import Path

        p = Path(path)
        if not p.is_absolute():
            p = base_dir / p
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": str(p)}

    if scheme == "mysql":
        import pymysql

        pymysql.install_as_MySQLdb()
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": parts.path.lstrip("/"),
            "USER": parts.username or "",
            "PASSWORD": parts.password or "",
            "HOST": parts.hostname or "localhost",
            "PORT": parts.port or 3306,
            "OPTIONS": {"charset": "utf8mb4"},
        }

    raise ValueError(f"Unsupported DATABASE_URL scheme: {parts.scheme!r}")
