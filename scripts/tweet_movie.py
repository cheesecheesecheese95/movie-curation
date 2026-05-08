#!/usr/bin/env python3
"""매일 자동 영화 추천 트윗 — GitHub Actions에서 실행"""
import sqlite3, json, os, tempfile, requests
import tweepy

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'curation.db')
POSTED_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'tweeted.json')

# v2 Client (트윗 게시)
client = tweepy.Client(
    consumer_key=os.environ['X_CONSUMER_KEY'],
    consumer_secret=os.environ['X_CONSUMER_SECRET'],
    access_token=os.environ['X_ACCESS_TOKEN'],
    access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET'],
)

# v1.1 API (미디어 업로드용)
auth = tweepy.OAuth1UserHandler(
    os.environ['X_CONSUMER_KEY'],
    os.environ['X_CONSUMER_SECRET'],
    os.environ['X_ACCESS_TOKEN'],
    os.environ['X_ACCESS_TOKEN_SECRET'],
)
api = tweepy.API(auth)


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
               m.vote_average, m.director, m.overview, m.poster_url,
               m.naver_rating, m.imdb_rating, m.rotten_tomatoes,
               m.cast_names
        FROM videos v
        JOIN movies m ON v.tmdb_id = m.tmdb_id
        WHERE v.content_type = 'summary'
          AND v.match_confidence >= 0.7
          AND m.vote_average >= 6.0
          AND m.poster_url IS NOT NULL
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

def upload_poster(poster_url):
    """TMDB 포스터를 다운로드해서 X에 업로드, media_id 반환"""
    r = requests.get(poster_url, timeout=15)
    if r.status_code != 200:
        return None
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        f.write(r.content)
        tmp_path = f.name
    try:
        media = api.media_upload(filename=tmp_path)
        return media.media_id
    finally:
        os.unlink(tmp_path)

def format_tweet(m):
    title = m['title_ko'] or m['title_en'] or ''
    year = m['year'] or ''
    link = f"https://dontwatchall.com/#movie/{m['tmdb_id']}"

    # 줄거리로 소개 문구 생성 (2~3문장)
    intro = ''
    if m['overview']:
        text = m['overview'].replace('...', '…')
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        # 2~3문장, 총 120자 이내
        picked = []
        total = 0
        for s in sentences:
            if total + len(s) > 120:
                break
            picked.append(s)
            total += len(s)
        if picked:
            intro = '. '.join(picked) + '.'

    lines = []
    if intro:
        lines.append(intro)
    lines.append('')
    lines.append(f'🎬 {title} ({year})')
    lines.append(f'🎞 결말포함 리뷰로 보기 → {link}')

    tweet = '\n'.join(lines)

    # 280자 제한
    if len(tweet) > 270:
        # 소개 문구 줄이기
        if intro:
            short = intro[:140] + '…'
            lines[0] = short
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

    # 포스터 업로드
    media_id = None
    if movie.get('poster_url'):
        try:
            media_id = upload_poster(movie['poster_url'])
            print(f"📸 포스터 업로드 완료: {media_id}")
        except Exception as e:
            print(f"⚠️ 포스터 업로드 실패: {e}")

    kwargs = {'text': tweet_text}
    if media_id:
        kwargs['media_ids'] = [media_id]
    resp = client.create_tweet(**kwargs)
    print(f"✅ 트윗 성공! ID: {resp.data['id']}")

    posted.add(movie['video_id'])
    save_posted(posted)
    print(f"📊 누적 포스팅: {len(posted)}건")

if __name__ == '__main__':
    main()
