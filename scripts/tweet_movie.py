#!/usr/bin/env python3
"""매일 자동 영화 추천 트윗 — GitHub Actions에서 실행"""
import sqlite3, json, random, os
import tweepy

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'curation.db')
POSTED_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'tweeted.json')

client = tweepy.Client(
    consumer_key=os.environ['X_CONSUMER_KEY'],
    consumer_secret=os.environ['X_CONSUMER_SECRET'],
    access_token=os.environ['X_ACCESS_TOKEN'],
    access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET'],
)

def load_posted():
    try:
        with open(POSTED_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def save_posted(posted):
    with open(POSTED_FILE, 'w') as f:
        json.dump(list(posted), f)

def pick_movie():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT v.video_id, v.title AS video_title, v.channel_name,
               m.tmdb_id, m.title_ko, m.title_en, m.year, m.genres,
               m.vote_average, m.director, m.overview,
               m.naver_rating, m.imdb_rating, m.rotten_tomatoes,
               m.cast_names
        FROM videos v
        JOIN movies m ON v.tmdb_id = m.tmdb_id
        WHERE v.content_type = 'summary'
          AND v.match_confidence >= 0.7
          AND m.vote_average >= 6.0
          AND (v.view_count > 5000 OR m.vote_count > 100)
        ORDER BY RANDOM()
    """).fetchall()
    conn.close()

    posted = load_posted()
    for row in rows:
        if row['video_id'] not in posted:
            return dict(row), posted
    posted.clear()
    return (dict(rows[0]), posted) if rows else (None, posted)

def format_tweet(m):
    title = m['title_ko'] or m['title_en'] or ''
    year = m['year'] or ''
    genres = json.loads(m['genres']) if m['genres'] else []
    genre_str = ' / '.join(g for g in genres[:2] if g not in ('TV 영화','음악','역사','가족','서부'))
    director = m['director'] or ''
    cast = json.loads(m['cast_names']) if m['cast_names'] else []
    cast_str = ', '.join(cast[:3])
    rating = m['vote_average']

    # 줄거리 첫 문장
    overview = ''
    if m['overview']:
        s = m['overview'].replace('...', '…').split('.')[0].strip()
        if len(s) > 70:
            s = s[:67] + '…'
        if s:
            overview = s + '.'

    # 링크
    link = f"https://dontwatchall.com/#movie/{m['tmdb_id']}"

    # 트윗 조합
    lines = []
    lines.append(f"🎬 {title} ({year})")
    lines.append("")

    info = []
    if rating:
        info.append(f"⭐ {rating:.1f}")
    if genre_str:
        info.append(genre_str)
    lines.append(' · '.join(info))

    if director:
        lines.append(f"🎬 {director} 감독")
    if cast_str:
        lines.append(f"🎭 {cast_str}")

    if overview:
        lines.append("")
        lines.append(f"📖 {overview}")

    lines.append("")
    lines.append(f"👉 {link}")
    lines.append("")
    lines.append("#영화추천 #결말포함 #영화리뷰")

    tweet = '\n'.join(lines)

    # 280자 제한
    if len(tweet) > 270:
        # 줄거리 제거
        lines = [l for l in lines if not l.startswith('📖')]
        tweet = '\n'.join(lines)

    return tweet

def main():
    result = pick_movie()
    if not result or not result[0]:
        print('추천할 영화 없음')
        return

    movie, posted = result
    tweet_text = format_tweet(movie)
    print(f"트윗 내용:\n{tweet_text}\n")

    try:
        resp = client.create_tweet(text=tweet_text)
        print(f"✅ 트윗 성공! ID: {resp.data['id']}")
    except Exception as e:
        # URL 차단 시 URL 없이 재시도
        if '403' in str(e):
            tweet_no_url = '\n'.join(l for l in tweet_text.split('\n') if not l.startswith('👉'))
            resp = client.create_tweet(text=tweet_no_url)
            print(f"✅ 트윗 성공 (URL 제외)! ID: {resp.data['id']}")
        else:
            raise

    posted.add(movie['video_id'])
    save_posted(posted)
    print(f"📊 누적 포스팅: {len(posted)}건")

if __name__ == '__main__':
    main()
