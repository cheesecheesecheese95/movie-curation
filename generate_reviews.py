#!/usr/bin/env python3
"""Claude Haiku로 영화별 AI 추천평 일괄 생성"""
import sqlite3, json, time, os
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY)
DB = 'data/curation.db'
BATCH = 5  # 한 프롬프트에 5편씩 묶어서 비용 절감

def get_movies_without_review():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT m.tmdb_id, m.title_ko, m.title_en, m.year, m.genres, m.overview,
               m.vote_average, m.vote_count, m.director, m.runtime
        FROM movies m
        JOIN videos v ON m.tmdb_id = v.tmdb_id
        WHERE m.ai_review IS NULL
          AND v.content_type = 'summary'
          AND v.match_confidence >= 0.5
        GROUP BY m.tmdb_id
        ORDER BY m.vote_count DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def generate_batch(movies):
    movie_list = ""
    for i, m in enumerate(movies):
        genres = m['genres'] or '[]'
        if isinstance(genres, str):
            try: genres = ', '.join(json.loads(genres))
            except: pass
        movie_list += f"""
---
[{i+1}] {m['title_ko'] or m['title_en']} ({m['year'] or '?'})
장르: {genres}
감독: {m['director'] or '정보없음'}
TMDB 평점: {m['vote_average'] or '?'} ({m['vote_count'] or 0}명)
러닝타임: {m['runtime'] or '?'}분
줄거리: {(m['overview'] or '정보없음')[:300]}
"""

    prompt = f"""아래 영화들에 대해 각각 블로그 리뷰 스타일의 추천평을 작성해주세요.

규칙:
- 각 영화당 3~5문장으로 작성
- 첫 줄: 이 영화의 핵심 매력을 한 문장으로 (예: "복수극의 정석을 보여주는 영화")
- 중간: 좋은 점 1~2가지를 구체적으로 (연출, 연기, 스토리, 반전, 분위기 등)
- 마지막: 아쉬운 점 하나 또는 추천 대상 (예: "다만 후반부 전개가 급한 편", "스릴러를 좋아하는 분이라면 꼭 보세요")
- 자연스러운 블로그/커뮤니티 리뷰 톤 (존댓말X, ~이다/~다 체)
- 스포일러 절대 금지
- 평점 숫자를 직접 언급하지 말 것

출력 형식 (JSON 배열):
[
  {{"id": 1, "review": "추천평 텍스트"}},
  ...
]

영화 목록:
{movie_list}
"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    # JSON 추출
    start = text.find('[')
    end = text.rfind(']') + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return []

def save_reviews(movies, reviews):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for r in reviews:
        idx = r.get('id', 0) - 1
        if 0 <= idx < len(movies):
            tmdb_id = movies[idx]['tmdb_id']
            review_text = r.get('review', '')
            if review_text:
                c.execute('UPDATE movies SET ai_review = ? WHERE tmdb_id = ?', (review_text, tmdb_id))
    conn.commit()
    conn.close()

def main():
    movies = get_movies_without_review()
    total = len(movies)
    print(f"리뷰 미생성 영화: {total}편")

    done = 0
    for i in range(0, total, BATCH):
        batch = movies[i:i+BATCH]
        print(f"\n[{i+1}~{min(i+BATCH, total)} / {total}] {', '.join(m['title_ko'] or m['title_en'] or '?' for m in batch)}")
        try:
            reviews = generate_batch(batch)
            save_reviews(batch, reviews)
            done += len(reviews)
            print(f"  ✅ {len(reviews)}편 생성 완료 (누적 {done})")
        except Exception as e:
            print(f"  ❌ 오류: {e}")
        time.sleep(0.5)  # rate limit

    print(f"\n🎬 완료: {done}/{total}편 리뷰 생성")

if __name__ == '__main__':
    main()
