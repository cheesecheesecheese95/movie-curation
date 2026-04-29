"""나머지 미매칭 영상 전체 처리 + 분류 + 보강 + 피드 생성"""
import json, time
import anthropic
from match_movies import match_all
from db import get_conn

# 1) 매칭 (200개씩 반복)
for i in range(4):
    conn = get_conn()
    r = conn.execute("SELECT COUNT(*) FROM videos WHERE tmdb_id IS NULL AND movie_title_extracted IS NULL").fetchone()[0]
    conn.close()
    if r == 0: break
    print(f"\n=== 매칭 라운드 {i+1}: {r}개 남음 ===")
    match_all()

# 2) 분류
print("\n=== 콘텐츠 분류 ===")
conn = get_conn()
rows = conn.execute("SELECT video_id, title, description FROM videos WHERE tmdb_id IS NOT NULL AND content_type IS NULL").fetchall()
vids = [dict(r) for r in rows]
print(f"{len(vids)}개 분류 필요")

if vids:
    client = anthropic.Anthropic()
    SYS = 'YouTube 영상을 summary(줄거리 요약/해설), review(감상/평가), other(기타)로 분류. JSON 배열로 응답: [{"video_id":"...","type":"summary"}]'
    for i in range(0, len(vids), 20):
        batch = vids[i:i+20]
        vlist = "\n".join(f'[{v["video_id"]}] {v["title"]}' for v in batch)
        try:
            resp = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=2000, system=SYS, messages=[{"role":"user","content":vlist}])
            text = resp.content[0].text
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            for r in json.loads(text.strip()):
                conn.execute("UPDATE videos SET content_type=? WHERE video_id=?", (r.get("type","other"), r["video_id"]))
            conn.commit()
            print(f"  ({i+1}~{i+len(batch)}) done")
        except Exception as e:
            print(f"  err: {e}")
        time.sleep(0.3)
conn.close()

# 3) 보강
print("\n=== 메타데이터 보강 ===")
from enrich import enrich_all
enrich_all()

# 4) 피드
print("\n=== 피드 생성 ===")
from export import export_feed
export_feed()
