#!/usr/bin/env python3
"""미매칭 변경사항 JSON을 DB에 반영"""
import sqlite3, json, sys, requests

TMDB_KEY = 'bd2b2b6abea0e1147089a78d8d05d348'
DB = 'data/curation.db'

def apply(filepath):
    with open(filepath) as f:
        changes = json.load(f)

    conn = sqlite3.connect(DB, timeout=30)
    c = conn.cursor()
    matched = 0
    deleted = 0

    for video_id, change in changes.items():
        if change == 'delete':
            c.execute('DELETE FROM videos WHERE video_id = ?', (video_id,))
            deleted += c.rowcount
            continue

        title = change.get('title', '')
        tmdb_id = change.get('tmdb_id')
        genre = change.get('genre', '')

        if tmdb_id:
            # TMDB에서 영화 정보 가져오기
            c.execute('SELECT tmdb_id FROM movies WHERE tmdb_id = ?', (tmdb_id,))
            if not c.fetchone():
                try:
                    r = requests.get(f'https://api.themoviedb.org/3/movie/{tmdb_id}',
                        params={'api_key': TMDB_KEY, 'language': 'ko-KR'}, timeout=10)
                    d = r.json()
                    if d.get('id'):
                        poster = 'https://image.tmdb.org/t/p/w500'+d['poster_path'] if d.get('poster_path') else None
                        year = int(d['release_date'][:4]) if d.get('release_date') else None
                        genres = json.dumps([genre] if genre else [g['name'] for g in d.get('genres', [])])
                        c.execute('''INSERT OR REPLACE INTO movies (tmdb_id, title_ko, title_en, year, genres, poster_url, vote_average, vote_count, overview, runtime)
                            VALUES (?,?,?,?,?,?,?,?,?,?)''',
                            (tmdb_id, d.get('title') or title, d.get('original_title'), year, genres, poster, d.get('vote_average'), d.get('vote_count'), d.get('overview'), d.get('runtime')))
                except Exception as e:
                    print(f'  ⚠️ TMDB 조회 실패 ({tmdb_id}): {e}')

            # 영상 매칭 + 신뢰도 0.9 + summary
            c.execute('''UPDATE videos SET tmdb_id = ?, movie_title_extracted = ?,
                content_type = 'summary', match_confidence = 0.9
                WHERE video_id = ?''', (tmdb_id, title or None, video_id))
            matched += c.rowcount
        elif title:
            c.execute('UPDATE videos SET movie_title_extracted = ? WHERE video_id = ?', (title, video_id))

    conn.commit()
    conn.close()
    print(f'✅ 반영 완료: 매칭 {matched}건, 삭제 {deleted}건')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('사용법: python apply_unmatched.py <변경사항.json>')
        sys.exit(1)
    apply(sys.argv[1])
