import sqlite3
from config import DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY,
        channel_id TEXT NOT NULL,
        channel_name TEXT,
        title TEXT,
        description TEXT,
        published_at TEXT,
        view_count INTEGER DEFAULT 0,
        duration_sec INTEGER DEFAULT 0,
        movie_title_extracted TEXT,
        tmdb_id INTEGER,
        match_confidence REAL,
        has_spoiler INTEGER,
        matched_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS movies (
        tmdb_id INTEGER PRIMARY KEY,
        title_ko TEXT,
        title_en TEXT,
        year INTEGER,
        genres TEXT,
        poster_url TEXT,
        vote_average REAL,
        vote_count INTEGER,
        overview TEXT,
        director TEXT,
        runtime INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
    CREATE INDEX IF NOT EXISTS idx_videos_tmdb ON videos(tmdb_id);
    CREATE INDEX IF NOT EXISTS idx_videos_unmatched ON videos(tmdb_id) WHERE tmdb_id IS NULL;
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("DB initialized at", DB_PATH)
