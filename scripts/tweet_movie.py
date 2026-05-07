#!/usr/bin/env python3
"""매일 자동 영화 추천 트윗 — GitHub Actions에서 실행"""
import sqlite3, json, random, os
import tweepy

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'curation.db')
POSTED_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'tweeted.json')

# 환경변수에서 키 로드
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
               m.title_ko, m.title_en, m.year, m.genres, m.vote_average,
               m.director, m.overview, m.naver_rating, m.imdb_rating, m.rotten_tomatoes
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
    # 전부 포스팅했으면 리셋
    posted.clear()
    return dict(rows[0]), posted if rows else (None, posted)

def format_tweet(m):
    title = m['title_ko'] or m['title_en'] or ''
    year = m['year'] or ''
    rating = f"⭐ {m['vote_average']:.1f}" if m['vote_average'] else ''
    genres = json.loads(m['genres']) if m['genres'] else []
    genre_str = ' · '.join(g for g in genres[:2] if g not in ('TV 영화','음악','역사','가족','서부'))
    director = m['director'] or ''

    # 평점 뱃지
    badges = []
    if m['vote_average']:
        badges.append(f"TMDB {m['vote_average']:.1f}")
    if m['imdb_rating']:
        badges.append(f"IMDb {m['imdb_rating']}")
    if m['rotten_tomatoes']:
        badges.append(f"🍅 {m['rotten_tomatoes']}%")
    if m['naver_rating']:
        badges.append(f"네이버 {m['naver_rating']}")
    badge_line = ' | '.join(badges)

    # 한줄 소개 (overview에서 첫 문장)
    intro = ''
    if m['overview']:
        sentences = m['overview'].replace('...', '…').split('.')
        s = sentences[0].strip()
        if len(s) > 80:
            s = s[:77] + '…'
        if s:
            intro = f"\n\n{s}."

    url = f"https://dontwatchall.com"

    tweet = f"🎬 {title} ({year})\n{rating}  {genre_str}"
    if director:
        tweet += f"  {director} 감독"
    if badge_line:
        tweet += f"\n{badge_line}"
    if intro:
        tweet += intro
    tweet += f"\n\n#영화추천 #결말포함 #{title.replace(' ', '').replace(':', '')}"

    # 280자 제한 (한글은 2자로 계산되므로 여유있게)
    if len(tweet) > 270:
        tweet = tweet[:267] + '...'

    return tweet

def main():
    result = pick_movie()
    if not result or not result[0]:
        print('추천할 영화 없음')
        return

    movie, posted = result
    tweet_text = format_tweet(movie)
    print(f"트윗 내용:\n{tweet_text}\n")

    resp = client.create_tweet(text=tweet_text)
    print(f"✅ 트윗 성공! ID: {resp.data['id']}")

    posted.add(movie['video_id'])
    save_posted(posted)
    print(f"📊 누적 포스팅: {len(posted)}건")

if __name__ == '__main__':
    main()
