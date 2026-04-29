"""Step 2: Claude API로 영상→영화 매칭 + TMDB 검색"""
import json, time, requests
import anthropic
from config import ANTHROPIC_API_KEY, TMDB_API_KEY
from db import get_conn, init_db

TMDB_SEARCH = "https://api.themoviedb.org/3/search/movie"

SYSTEM_PROMPT = """당신은 유튜브 영화 리뷰/요약 영상의 메타데이터를 분석하여 해당 영상이 다루는 영화를 식별하는 전문가입니다.

규칙:
1. 영상 제목과 설명에서 다루는 영화의 정확한 제목을 추출하세요.
2. 한국어 제목과 영어 제목 모두 가능하면 제공하세요.
3. 영화가 아닌 드라마, 예능, 게임 등은 movie_title을 null로 설정하세요.
4. 여러 영화를 다루는 영상이면 가장 주된 영화 1개만 선택하세요.
5. 결말을 포함하는지(has_spoiler) 제목/설명의 단서로 판단하세요. ("결말", "엔딩", "스포", "반전" 등)
6. confidence는 0~1 사이로, 영화 식별이 확실하면 0.9+, 애매하면 0.5 이하."""

USER_TEMPLATE = """아래 유튜브 영상들의 제목과 설명을 분석하여 각 영상이 다루는 영화를 식별해주세요.

{video_list}

JSON 배열로 응답해주세요. 각 항목:
{{"video_id": "...", "movie_title": "한국어 제목", "movie_title_en": "English Title", "movie_year": 2024, "confidence": 0.95, "has_spoiler": true}}

영화가 아닌 콘텐츠(드라마, 예능 등)이면 movie_title을 null로."""


def get_unmatched_videos(limit=100):
    conn = get_conn()
    rows = conn.execute("""
        SELECT video_id, title, description FROM videos
        WHERE tmdb_id IS NULL AND movie_title_extracted IS NULL
        ORDER BY published_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def extract_movies_batch(videos, batch_size=10):
    """Claude API로 배치 매칭"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    all_results = []

    for i in range(0, len(videos), batch_size):
        batch = videos[i:i+batch_size]
        video_list = "\n\n".join(
            f"[{v['video_id']}]\n제목: {v['title']}\n설명: {(v['description'] or '')[:300]}"
            for v in batch
        )

        print(f"  Claude API 호출 ({i+1}~{i+len(batch)}/{len(videos)})...", end=" ")
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": USER_TEMPLATE.format(video_list=video_list)}],
            )
            text = resp.content[0].text
            # JSON 추출 (```json ... ``` 또는 순수 JSON)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            results = json.loads(text.strip())
            all_results.extend(results)
            print(f"✅ {len(results)}개 매칭")
        except Exception as e:
            print(f"❌ {e}")

        time.sleep(0.5)  # rate limit 여유

    return all_results


def search_tmdb(title, year=None):
    """TMDB에서 영화 검색"""
    params = {"api_key": TMDB_API_KEY, "query": title, "language": "ko-KR"}
    if year:
        params["year"] = year
    try:
        r = requests.get(TMDB_SEARCH, params=params, timeout=10)
        data = r.json()
        results = data.get("results", [])
        if results:
            return results[0]  # 가장 관련성 높은 결과
    except:
        pass
    # 한국어로 못 찾으면 영어로 재시도
    params["language"] = "en-US"
    try:
        r = requests.get(TMDB_SEARCH, params=params, timeout=10)
        data = r.json()
        results = data.get("results", [])
        if results:
            return results[0]
    except:
        pass
    return None


def match_all():
    init_db()
    videos = get_unmatched_videos(limit=200)
    if not videos:
        print("매칭할 영상이 없습니다.")
        return

    print(f"🎯 {len(videos)}개 영상 매칭 시작...")

    # Claude로 영화 제목 추출
    matches = extract_movies_batch(videos)

    # TMDB 매칭
    conn = get_conn()
    matched = 0
    for m in matches:
        vid = m.get("video_id")
        title = m.get("movie_title")
        title_en = m.get("movie_title_en")
        year = m.get("movie_year")
        confidence = m.get("confidence", 0)
        has_spoiler = 1 if m.get("has_spoiler") else 0

        if not title:
            # 영화가 아닌 콘텐츠
            conn.execute("""
                UPDATE videos SET movie_title_extracted = '[non-movie]', match_confidence = 0,
                    matched_at = datetime('now') WHERE video_id = ?
            """, (vid,))
            continue

        # TMDB 검색
        tmdb = search_tmdb(title, year) or (search_tmdb(title_en, year) if title_en else None)
        tmdb_id = tmdb["id"] if tmdb else None

        conn.execute("""
            UPDATE videos SET movie_title_extracted = ?, tmdb_id = ?,
                match_confidence = ?, has_spoiler = ?, matched_at = datetime('now')
            WHERE video_id = ?
        """, (title, tmdb_id, confidence, has_spoiler, vid))

        if tmdb_id:
            matched += 1
            print(f"  ✅ {title} → TMDB #{tmdb_id}")
        else:
            print(f"  ⚠️ {title} → TMDB 미발견")

    conn.commit()
    conn.close()
    print(f"\n📊 결과: {matched}/{len(matches)} TMDB 매칭 성공")


if __name__ == "__main__":
    match_all()
