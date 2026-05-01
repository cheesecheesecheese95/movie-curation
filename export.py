"""Step 4: JSON 피드 생성"""
import json
from config import FEED_PATH
from db import get_conn, init_db


def export_feed():
    init_db()
    conn = get_conn()

    rows = conn.execute("""
        SELECT v.video_id, v.channel_id, v.channel_name, v.title AS video_title,
               v.published_at, v.view_count, v.duration_sec, v.match_confidence,
               v.has_spoiler,
               m.tmdb_id, m.title_ko, m.title_en, m.year, m.genres,
               m.poster_url, m.vote_average, m.vote_count, m.overview,
               m.director, m.runtime,
               m.imdb_rating, m.rotten_tomatoes, m.metacritic, m.watch_providers
        FROM videos v
        JOIN movies m ON v.tmdb_id = m.tmdb_id
        WHERE v.tmdb_id IS NOT NULL AND v.match_confidence >= 0.5
              AND v.content_type = 'summary'
        ORDER BY v.published_at DESC
    """).fetchall()

    items = []
    for r in rows:
        items.append({
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
            },
        })

    conn.close()

    feed = {
        "total": len(items),
        "items": items,
    }

    with open(FEED_PATH, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

    print(f"✅ 피드 생성 완료: {len(items)}개 항목 → {FEED_PATH}")

    # 요약 통계
    if items:
        genres_all = [g for i in items for g in i["movie"]["genres"]]
        from collections import Counter
        top_genres = Counter(genres_all).most_common(5)
        channels = set(i["video"]["channel"] for i in items)
        print(f"📊 채널 {len(channels)}개 | 장르 TOP: {', '.join(f'{g}({c})' for g,c in top_genres)}")


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
