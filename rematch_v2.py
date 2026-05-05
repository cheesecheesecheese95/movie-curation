#!/usr/bin/env python3
"""미매칭 영상 재매칭 v2 — description + 업로더 댓글 포함"""
import sqlite3, json, time, requests, os
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY
from googleapiclient.discovery import build

TMDB_KEY = 'bd2b2b6abea0e1147089a78d8d05d348'
YT_KEY = os.environ.get('YOUTUBE_API_KEY', '')
DB = 'data/curation.db'
BATCH = 5  # description이 길어서 배치 줄임

client = Anthropic(api_key=ANTHROPIC_API_KEY)
yt = None

def init_yt():
    global yt
    if YT_KEY:
        yt = build('youtube', 'v3', developerKey=YT_KEY)

def get_video_details(video_ids):
    """YouTube API로 description + 업로더 댓글 가져오기"""
    if not yt:
        return {}

    details = {}
    # 1) 영상 상세 (description)
    try:
        resp = yt.videos().list(part='snippet', id=','.join(video_ids)).execute()
        for item in resp.get('items', []):
            vid = item['id']
            details[vid] = {
                'description': (item['snippet'].get('description') or '')[:500],
                'uploader_comment': ''
            }
    except Exception as e:
        print(f"  ⚠️ YouTube API 오류: {e}")
        return {}

    # 2) 업로더 첫 댓글 (고정 댓글 포함)
    for vid in video_ids:
        try:
            resp = yt.commentThreads().list(
                part='snippet', videoId=vid, maxResults=5, order='relevance'
            ).execute()
            for thread in resp.get('items', []):
                snippet = thread['snippet']['topLevelComment']['snippet']
                # 업로더 댓글인지 확인
                if snippet.get('authorChannelId', {}).get('value') == thread['snippet'].get('videoOwnerChannelId'):
                    if vid in details:
                        details[vid]['uploader_comment'] = snippet.get('textDisplay', '')[:300]
                    break
        except:
            pass  # 댓글 비활성화 등

    return details

def get_unmatched():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT video_id, title, channel_name, duration_sec
        FROM videos
        WHERE tmdb_id IS NULL
        AND (title LIKE '%결말%' OR title LIKE '%요약%' OR title LIKE '%줄거리%' OR title LIKE '%스포%')
        AND duration_sec >= 180 AND duration_sec <= 3600
        ORDER BY view_count DESC""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def extract_titles(videos, details):
    video_list = ""
    for i, v in enumerate(videos):
        d = details.get(v['video_id'], {})
        desc = d.get('description', '')
        comment = d.get('uploader_comment', '')

        video_list += f"[{i+1}] 제목: {v['title']}\n"
        video_list += f"채널: {v['channel_name']} · {v['duration_sec']//60}분\n"
        if desc:
            video_list += f"설명: {desc}\n"
        if comment:
            video_list += f"업로더 댓글: {comment}\n"
        video_list += "\n"

    prompt = f"""아래 유튜브 영상들의 제목, 설명, 업로더 댓글을 분석해서 각 영상이 다루는 영화의 정확한 제목을 추출해주세요.

규칙:
- 한국어 제목을 우선으로, 영어 원제도 함께 알려주세요
- 설명란에 영화 제목이 명시된 경우 그것을 우선 사용
- 드라마, 웹드라마, 웹툰, 예능, 애니메이션 시리즈(TV)는 is_movie: false
- 극장판 애니메이션은 is_movie: true
- 영화가 아닌 콘텐츠(뉴스, 교양, 먹방, 게임 등)는 is_movie: false
- 여러 영화를 다루는 몰아보기는 is_movie: false
- 확실하지 않으면 is_movie: false로 표시 (억지로 매칭하지 말 것)

출력 형식 (JSON 배열만, 다른 텍스트 없이):
[{{"id":1,"title_ko":"한국어제목","title_en":"English Title","is_movie":true}},{{"id":2,"title_ko":"","title_en":"","is_movie":false}}]

영상 목록:
{video_list}"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    start = text.find('[')
    end = text.rfind(']') + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            import re
            cleaned = re.sub(r',\s*]', ']', text[start:end])
            cleaned = re.sub(r'}\s*{', '},{', cleaned)
            try:
                return json.loads(cleaned)
            except:
                return []
    return []

def search_tmdb(title_ko, title_en=""):
    for query in [title_ko, title_en]:
        if not query or len(query) < 2:
            continue
        try:
            r = requests.get('https://api.themoviedb.org/3/search/movie',
                params={'api_key': TMDB_KEY, 'query': query, 'language': 'ko-KR'}, timeout=10)
            results = r.json().get('results', [])
            if results:
                return results[0]
        except:
            pass
    return None

def main():
    init_yt()
    if not yt:
        print("⚠️ YOUTUBE_API_KEY 없음 — description 없이 진행")

    videos = get_unmatched()
    print(f"미매칭 영상: {len(videos)}개")

    conn = sqlite3.connect(DB, timeout=30)
    c = conn.cursor()
    matched = 0
    skipped = 0

    for i in range(0, len(videos), BATCH):
        batch = videos[i:i+BATCH]
        batch_ids = [v['video_id'] for v in batch]

        # YouTube API로 상세정보 가져오기
        details = get_video_details(batch_ids) if yt else {}

        titles_str = ', '.join(v['title'][:30] for v in batch)
        print(f"\n[{i+1}~{min(i+BATCH, len(videos))} / {len(videos)}] {titles_str[:80]}")

        try:
            results = extract_titles(batch, details)
        except Exception as e:
            print(f"  ❌ Claude 오류: {e}")
            time.sleep(1)
            continue

        for r in results:
            idx = r.get('id', 0) - 1
            if idx < 0 or idx >= len(batch):
                continue
            v = batch[idx]
            title_ko = r.get('title_ko', '')
            title_en = r.get('title_en', '')
            is_movie = r.get('is_movie', False)

            if not is_movie or not title_ko:
                c.execute("UPDATE videos SET movie_title_extracted = '[non-movie]' WHERE video_id = ?", (v['video_id'],))
                skipped += 1
                continue

            tmdb = search_tmdb(title_ko, title_en)
            if tmdb:
                tmdb_id = tmdb['id']
                c.execute('SELECT tmdb_id FROM movies WHERE tmdb_id = ?', (tmdb_id,))
                if not c.fetchone():
                    poster = 'https://image.tmdb.org/t/p/w500'+tmdb['poster_path'] if tmdb.get('poster_path') else None
                    year = int(tmdb['release_date'][:4]) if tmdb.get('release_date') else None
                    c.execute('''INSERT OR IGNORE INTO movies (tmdb_id, title_ko, title_en, year, poster_url, vote_average, vote_count, overview)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (tmdb_id, tmdb.get('title'), tmdb.get('original_title'), year, poster, tmdb.get('vote_average'), tmdb.get('vote_count'), tmdb.get('overview')))

                c.execute("""UPDATE videos SET tmdb_id=?, movie_title_extracted=?,
                    content_type='summary', match_confidence=0.88
                    WHERE video_id=?""", (tmdb_id, title_ko, v['video_id']))
                matched += 1
                print(f"  ✅ {title_ko} → tmdb:{tmdb_id}")
            else:
                c.execute("UPDATE videos SET movie_title_extracted = ? WHERE video_id = ?", (title_ko, v['video_id']))
                print(f"  ⚠️ {title_ko} → TMDB 미발견")

        conn.commit()
        time.sleep(0.3)

    conn.close()
    print(f"\n🎬 완료: 매칭 {matched} / 비영화 {skipped} / 전체 {len(videos)}")

if __name__ == '__main__':
    main()
