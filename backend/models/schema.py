import os
import re

import asyncpg

DATA_DIR = os.environ.get("DATA_DIR", "/data")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://lumalife:lumalife@localhost:5432/lumalife")

# Global connection pool
_pool: asyncpg.Pool | None = None


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
    return user_dir


async def get_pool() -> asyncpg.Pool:
    """Get the global connection pool."""
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


async def init_db():
    """Initialize connection pool and create tables."""
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

    async with _pool.acquire() as conn:
        # Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Create users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create photos table with user_id
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                width INTEGER,
                height INTEGER,
                exif_date TEXT,
                orientation INTEGER,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                processed BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        # Create faces table with embedding vector column
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id TEXT PRIMARY KEY,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                crop_path TEXT NOT NULL,
                bbox_x INTEGER NOT NULL,
                bbox_y INTEGER NOT NULL,
                bbox_w INTEGER NOT NULL,
                bbox_h INTEGER NOT NULL,
                confidence REAL NOT NULL,
                cluster_id INTEGER,
                is_target BOOLEAN NOT NULL DEFAULT FALSE,
                embedding vector(512)
            )
        """)

        # Create clusters table with user_id
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id),
                face_count INTEGER NOT NULL DEFAULT 0,
                is_target BOOLEAN NOT NULL DEFAULT FALSE,
                confirmed_at TIMESTAMPTZ,
                PRIMARY KEY (id, user_id)
            )
        """)

        # Create tags table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                year INTEGER NOT NULL,
                month INTEGER,
                tagged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(photo_id)
            )
        """)

        # Create age_estimates table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS age_estimates (
                id SERIAL PRIMARY KEY,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                face_id TEXT NOT NULL REFERENCES faces(id) ON DELETE CASCADE,
                estimated_age REAL NOT NULL,
                estimated_year INTEGER,
                confidence REAL,
                method TEXT NOT NULL DEFAULT 'deepface',
                UNIQUE(photo_id)
            )
        """)

        # Create timeline_entries table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS timeline_entries (
                id SERIAL PRIMARY KEY,
                photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                estimated_year INTEGER NOT NULL,
                era_label TEXT NOT NULL,
                era_start INTEGER NOT NULL,
                era_end INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(photo_id)
            )
        """)

        # Create processing_state table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS processing_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Negative feedback: faces that should NOT be in the same cluster
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cluster_exclusions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                face_id_kept TEXT NOT NULL,
                face_id_removed TEXT NOT NULL,
                embedding_removed vector(512),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


async def close_db():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_or_create_user(username: str) -> int:
    """Get or create a user, returning the user_id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO users (username) VALUES ($1)
               ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
               RETURNING id""",
            username,
        )
        return row["id"]
