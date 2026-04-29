"""Step 3: TMDB 메타데이터 보강"""
import json, requests
from config import TMDB_API_KEY
from db import get_conn, init_db

TMDB_DETAIL = "https://api.themoviedb.org/3/movie/{tmdb_id}"
TMDB_CREDITS = "https://api.themoviedb.org/3/movie/{tmdb_id}/credits"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"


def get_unenriched_movies():
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT v.tmdb_id FROM videos v
        LEFT JOIN movies m ON v.tmdb_id = m.tmdb_id
        WHERE v.tmdb_id IS NOT NULL AND m.tmdb_id IS NULL
    """).fetchall()
    conn.close()
    return [r[0] for r in rows]


def fetch_movie_detail(tmdb_id):
    headers = {"accept": "application/json"}
    params = {"api_key": TMDB_API_KEY, "language": "ko-KR"}

    # 상세 정보
    r = requests.get(TMDB_DETAIL.format(tmdb_id=tmdb_id), params=params, timeout=10)
    if r.status_code != 200:
        return None
    d = r.json()

    # 영어 제목
    params_en = {"api_key": TMDB_API_KEY, "language": "en-US"}
    r_en = requests.get(TMDB_DETAIL.format(tmdb_id=tmdb_id), params=params_en, timeout=10)
    title_en = r_en.json().get("title", "") if r_en.status_code == 200 else ""

    # 크레딧 (감독)
    r_credits = requests.get(TMDB_CREDITS.format(tmdb_id=tmdb_id), params={"api_key": TMDB_API_KEY}, timeout=10)
    director = ""
    if r_credits.status_code == 200:
        crew = r_credits.json().get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        director = ", ".join(directors[:2])

    genres = json.dumps([g["name"] for g in d.get("genres", [])], ensure_ascii=False)
    poster = (TMDB_IMG + d["poster_path"]) if d.get("poster_path") else ""
    year = int(d["release_date"][:4]) if d.get("release_date") and len(d["release_date"]) >= 4 else None

    return {
        "tmdb_id": tmdb_id,
        "title_ko": d.get("title", ""),
        "title_en": title_en,
        "year": year,
        "genres": genres,
        "poster_url": poster,
        "vote_average": d.get("vote_average", 0),
        "vote_count": d.get("vote_count", 0),
        "overview": (d.get("overview") or "")[:500],
        "director": director,
        "runtime": d.get("runtime", 0),
    }


def enrich_all():
    init_db()
    ids = get_unenriched_movies()
    if not ids:
        print("보강할 영화가 없습니다.")
        return

    print(f"🎬 {len(ids)}개 영화 메타데이터 보강 시작...")
    conn = get_conn()
    enriched = 0

    for tmdb_id in ids:
        detail = fetch_movie_detail(tmdb_id)
        if not detail:
            print(f"  ⚠️ TMDB #{tmdb_id} 조회 실패")
            continue

        conn.execute("""
            INSERT OR REPLACE INTO movies (tmdb_id, title_ko, title_en, year, genres,
                poster_url, vote_average, vote_count, overview, director, runtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            detail["tmdb_id"], detail["title_ko"], detail["title_en"], detail["year"],
            detail["genres"], detail["poster_url"], detail["vote_average"],
            detail["vote_count"], detail["overview"], detail["director"], detail["runtime"],
        ))
        enriched += 1
        print(f"  ✅ {detail['title_ko']} ({detail['year']}) — {detail['director']}")

    conn.commit()
    conn.close()
    print(f"\n📊 보강 완료: {enriched}/{len(ids)}")


if __name__ == "__main__":
    enrich_all()
