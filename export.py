"""피드 JSON 생성 — 장르별 분할 + 메인 피드"""
import json, os, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "curation.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

HIDDEN_GENRES = {'TV 영화', '음악', '역사', '가족', '서부'}

def export_feed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT v.video_id, v.channel_id, v.channel_name, v.title AS video_title,
               v.published_at, v.view_count, v.duration_sec, v.match_confidence,
               v.has_spoiler,
               m.tmdb_id, m.title_ko, m.title_en, m.year, m.genres,
               m.poster_url, m.vote_average, m.vote_count, m.overview,
               m.director, m.runtime,
               m.imdb_rating, m.rotten_tomatoes, m.metacritic, m.watch_providers,
               m.naver_rating, m.ai_review
        FROM videos v
        JOIN movies m ON v.tmdb_id = m.tmdb_id
        WHERE v.tmdb_id IS NOT NULL AND v.match_confidence >= 0.5
              AND v.content_type = 'summary'
        ORDER BY v.published_at DESC
    """).fetchall()

    items = []
    for r in rows:
        item = {
            "video": {
                "id": r["video_id"],
                "title": r["video_title"],
                "url": f"https://www.youtube.com/watch?v={r['video_id']}",
                "embed_url": f"https://www.youtube.com/embed/{r['video_id']}",
                "channel": r["channel_name"],
                "channel_id": r["channel_id"],
                "published_at": r["published_at"],
                "view_count": r["view_count"],
                "duration_sec": r["duration_sec"],
                "duration_label": fmt_duration(r["duration_sec"]),
                "has_spoiler": bool(r["has_spoiler"]),
                "match_confidence": r["match_confidence"],
            },
            "movie": {
                "tmdb_id": r["tmdb_id"],
                "title_ko": r["title_ko"],
                "title_en": r["title_en"],
                "year": r["year"],
                "genres": json.loads(r["genres"]) if r["genres"] else [],
                "poster_url": r["poster_url"],
                "vote_average": r["vote_average"],
                "vote_count": r["vote_count"],
                "overview": r["overview"],
                "director": r["director"],
                "runtime": r["runtime"],
                "imdb_rating": r["imdb_rating"],
                "rotten_tomatoes": r["rotten_tomatoes"],
                "metacritic": r["metacritic"],
                "watch_providers": json.loads(r["watch_providers"]) if r["watch_providers"] else [],
                "naver_rating": r["naver_rating"],
                "ai_review": r["ai_review"],
            },
        }
        items.append(item)

    conn.close()

    # 1. 메인 피드 (전체)
    feed = {"total": len(items), "items": items}
    with open(os.path.join(DATA_DIR, "feed.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False)

    # 2. 장르별 분할
    genre_items = {}
    for item in items:
        for g in item["movie"]["genres"]:
            if g in HIDDEN_GENRES:
                continue
            if g not in genre_items:
                genre_items[g] = []
            genre_items[g].append(item)

    genre_dir = os.path.join(DATA_DIR, "genres")
    os.makedirs(genre_dir, exist_ok=True)

    genre_index = {}
    for genre, gitems in genre_items.items():
        safe_name = genre.replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}.json"
        with open(os.path.join(genre_dir, filename), "w", encoding="utf-8") as f:
            json.dump({"genre": genre, "total": len(gitems), "items": gitems}, f, ensure_ascii=False)
        genre_index[genre] = {"file": f"genres/{filename}", "count": len(gitems)}

    # 3. 장르 인덱스
    with open(os.path.join(DATA_DIR, "genres.json"), "w", encoding="utf-8") as f:
        json.dump(genre_index, f, ensure_ascii=False, indent=2)

    print(f"✅ 피드 생성 완료: {len(items)}개 항목 → {os.path.join(DATA_DIR, 'feed.json')}")

    channels = set(i["video"]["channel"] for i in items)
    genre_counts = {}
    for i in items:
        for g in i["movie"]["genres"]:
            if g not in HIDDEN_GENRES:
                genre_counts[g] = genre_counts.get(g, 0) + 1
    top_genres = sorted(genre_counts.items(), key=lambda x: -x[1])[:5]
    print(f"📊 채널 {len(channels)}개 | 장르 TOP: {', '.join(f'{g}({c})' for g,c in top_genres)}")
    print(f"📂 장르별 분할: {len(genre_items)}개 파일")


def fmt_duration(sec):
    if not sec:
        return ""
    h, m = divmod(sec, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h}시간 {m}분"
    return f"{m}분"


if __name__ == "__main__":
    export_feed()
