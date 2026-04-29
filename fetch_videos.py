"""Step 1: YouTube API로 시드 채널의 최근 영상 수집"""
import re, isodate
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY, load_seed_channels
from db import get_conn, init_db

def parse_duration(iso):
    """ISO 8601 duration → 초"""
    try:
        return int(isodate.parse_duration(iso).total_seconds())
    except:
        # isodate 없을 경우 수동 파싱
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
        if not m: return 0
        h, mi, s = (int(x) if x else 0 for x in m.groups())
        return h*3600 + mi*60 + s

def fetch_all():
    init_db()
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    channels = load_seed_channels()
    conn = get_conn()

    total_new = 0
    for ch in channels:
        cid = ch["channel_id"]
        name = ch.get("yt_title") or ch["name"]
        print(f"  [{name}]", end=" ")

        # uploads 플레이리스트 ID
        uploads_id = "UU" + cid[2:]  # UC... → UU...

        # 최근 50개 영상 ID 수집
        video_ids = []
        try:
            resp = yt.playlistItems().list(
                part="contentDetails", playlistId=uploads_id, maxResults=50
            ).execute()
            video_ids = [i["contentDetails"]["videoId"] for i in resp.get("items", [])]
        except Exception as e:
            print(f"skip ({e})")
            continue

        if not video_ids:
            print("0 videos")
            continue

        # 이미 DB에 있는 것 제외
        placeholders = ",".join("?" * len(video_ids))
        existing = set(r[0] for r in conn.execute(
            f"SELECT video_id FROM videos WHERE video_id IN ({placeholders})", video_ids
        ).fetchall())
        new_ids = [v for v in video_ids if v not in existing]

        if not new_ids:
            print(f"0 new / {len(video_ids)} total")
            continue

        # 영상 상세 정보 (50개씩 배치)
        inserted = 0
        for i in range(0, len(new_ids), 50):
            batch = new_ids[i:i+50]
            detail = yt.videos().list(
                part="snippet,contentDetails,statistics", id=",".join(batch)
            ).execute()

            for item in detail.get("items", []):
                vid = item["id"]
                sn = item["snippet"]
                stats = item.get("statistics", {})
                dur = parse_duration(item.get("contentDetails", {}).get("duration", ""))

                conn.execute("""
                    INSERT OR IGNORE INTO videos (video_id, channel_id, channel_name, title, description,
                        published_at, view_count, duration_sec)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vid, cid, name,
                    sn.get("title", ""), (sn.get("description") or "")[:2000],
                    sn.get("publishedAt", ""),
                    int(stats.get("viewCount", 0)),
                    dur,
                ))
                inserted += 1

        conn.commit()
        total_new += inserted
        print(f"{inserted} new / {len(video_ids)} total")

    conn.close()
    print(f"\n✅ 수집 완료: 신규 {total_new}개")

if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    print("🎬 영상 수집 시작...")
    fetch_all()
