import os, json

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "curation.db")
FEED_PATH = os.path.join(os.path.dirname(__file__), "data", "feed.json")
SEED_PATH = os.path.join(os.path.dirname(__file__), "seed_channels.json")

def load_seed_channels():
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
