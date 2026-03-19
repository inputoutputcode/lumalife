import os
import re
import aiosqlite

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def _sanitize_username(username: str) -> str:
    """Sanitize username to safe directory name."""
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', username.strip().lower())
    return name[:64] or "default"


def get_user_dir(username: str) -> str:
    """Get the data directory for a user, creating subdirs if needed."""
    safe_name = _sanitize_username(username)
    user_dir = os.path.join(DATA_DIR, "users", safe_name)
    os.makedirs(os.path.join(user_dir, "uploads"), exist_ok=True)
    os.makedirs(os.path.join(user_dir, "processed"), exist_ok=True)
    os.makedirs(os.path.join(user_dir, "embeddings"), exist_ok=True)
    return user_dir


def get_db_path(username: str = "default") -> str:
    user_dir = get_user_dir(username)
    return os.path.join(user_dir, "lumalife.db")


async def get_db(username: str = "default") -> aiosqlite.Connection:
    db_path = get_db_path(username)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    # Auto-init tables
    await _create_tables(db)
    return db


async def _create_tables(db: aiosqlite.Connection):
    """Create tables if they don't exist."""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            width INTEGER,
            height INTEGER,
            exif_date TEXT,
            orientation INTEGER,
            uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
            processed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS faces (
            id TEXT PRIMARY KEY,
            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            crop_path TEXT NOT NULL,
            embedding_path TEXT NOT NULL,
            bbox_x INTEGER NOT NULL,
            bbox_y INTEGER NOT NULL,
            bbox_w INTEGER NOT NULL,
            bbox_h INTEGER NOT NULL,
            confidence REAL NOT NULL,
            cluster_id INTEGER,
            is_target INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS clusters (
            id INTEGER PRIMARY KEY,
            face_count INTEGER NOT NULL DEFAULT 0,
            is_target INTEGER NOT NULL DEFAULT 0,
            confirmed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            tagged_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(photo_id)
        );

        CREATE TABLE IF NOT EXISTS age_estimates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            face_id TEXT NOT NULL REFERENCES faces(id) ON DELETE CASCADE,
            estimated_age REAL NOT NULL,
            estimated_year INTEGER,
            confidence REAL,
            method TEXT NOT NULL DEFAULT 'deepface',
            UNIQUE(photo_id)
        );

        CREATE TABLE IF NOT EXISTS timeline_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            estimated_year INTEGER NOT NULL,
            era_label TEXT NOT NULL,
            era_start INTEGER NOT NULL,
            era_end INTEGER NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(photo_id)
        );

        CREATE TABLE IF NOT EXISTS processing_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    await db.commit()


async def init_db():
    """Init default DB (for backward compat)."""
    db = await get_db("default")
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                width INTEGER,
                height INTEGER,
                exif_date TEXT,
                orientation INTEGER,
                uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
                processed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS faces (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                crop_path TEXT NOT NULL,
                embedding_path TEXT NOT NULL,
                bbox_x INTEGER NOT NULL,
                bbox_y INTEGER NOT NULL,
                bbox_w INTEGER NOT NULL,
                bbox_h INTEGER NOT NULL,
                confidence REAL NOT NULL,
                cluster_id INTEGER,
                is_target INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER PRIMARY KEY,
                face_count INTEGER NOT NULL DEFAULT 0,
                is_target INTEGER NOT NULL DEFAULT 0,
                confirmed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                year INTEGER NOT NULL,
                tagged_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(photo_id)
            );

            CREATE TABLE IF NOT EXISTS age_estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                face_id TEXT NOT NULL REFERENCES faces(id) ON DELETE CASCADE,
                estimated_age REAL NOT NULL,
                estimated_year INTEGER,
                confidence REAL,
                method TEXT NOT NULL DEFAULT 'deepface',
                UNIQUE(photo_id)
            );

            CREATE TABLE IF NOT EXISTS timeline_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                estimated_year INTEGER NOT NULL,
                era_label TEXT NOT NULL,
                era_start INTEGER NOT NULL,
                era_end INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(photo_id)
            );

            CREATE TABLE IF NOT EXISTS processing_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await db.commit()
    finally:
        await db.close()
