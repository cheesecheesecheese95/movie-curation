"""키워드 기반 대량 영상 수집 — 결말포함/요약 영상을 YouTube 검색으로 수집"""
import re, time
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY
from db import get_conn, init_db

# 검색 키워드 조합 (다양한 콘텐츠 커버)
SEARCH_QUERIES = [
    # 영화 결말포함
    "영화 결말포함", "영화 결말 포함 리뷰", "영화 결말포함 요약",
    "영화 스포 리뷰", "영화 몰아보기 결말",
    # 넷플릭스/OTT
    "넷플릭스 결말포함", "넷플릭스 영화 요약 결말", "넷플릭스 드라마 결말포함",
    "디즈니플러스 결말포함", "왓챠 결말포함", "쿠팡플레이 결말포함",
    # 드라마
    "드라마 결말포함", "한국드라마 결말포함 요약", "미드 결말포함",
    "일드 결말포함", "드라마 몰아보기 결말",
    # 장르별
    "공포영화 결말포함", "스릴러 결말포함", "SF영화 결말포함",
    "로맨스 결말포함", "액션영화 결말포함",
    # 인기/추천 형태
    "영화 요약 추천", "영화 리뷰 결말", "영화 해설 결말포함",
    "한방에 몰아보기", "영화 3분 요약",
]

def parse_duration(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m: return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h*3600 + mi*60 + s


def fetch_by_search(max_per_query=100):
    """키워드 검색으로 영상 수집"""
    init_db()
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    conn = get_conn()

    total_new = 0
    seen_ids = set()

    # 기존 DB 영상 ID
    existing = set(r[0] for r in conn.execute("SELECT video_id FROM videos").fetchall())
    print(f"기존 DB: {len(existing)}개")

    for qi, query in enumerate(SEARCH_QUERIES, 1):
        print(f"\n[{qi}/{len(SEARCH_QUERIES)}] 🔍 '{query}'")
        page_token = None
        fetched = 0

        while fetched < max_per_query:
            try:
                params = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": 50,
                    "order": "relevance",
                    "relevanceLanguage": "ko",
                    "videoDuration": "medium",  # 4~20분 (shorts 제외)
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = yt.search().list(**params).execute()
                items = resp.get("items", [])
                if not items:
                    break

                # 중복 제외
                video_ids = []
                for item in items:
                    vid = item["id"]["videoId"]
                    if vid not in existing and vid not in seen_ids:
                        video_ids.append(vid)
                        seen_ids.add(vid)

                if not video_ids:
                    page_token = resp.get("nextPageToken")
                    if not page_token:
                        break
                    fetched += len(items)
                    continue

                # 상세 정보
                detail = yt.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=",".join(video_ids)
                ).execute()

                batch_new = 0
                for item in detail.get("items", []):
                    vid = item["id"]
                    sn = item["snippet"]
                    stats = item.get("statistics", {})
                    dur = parse_duration(item.get("contentDetails", {}).get("duration", ""))

                    # 최소 1분 이상인 영상만
                    if dur < 60:
                        continue

                    title = sn.get("title", "")
                    desc = (sn.get("description") or "")[:2000]
                    channel = sn.get("channelTitle", "")
                    channel_id = sn.get("channelId", "")

                    # 결말포함 여부 자동 태깅
                    text = (title + " " + desc).lower()
                    has_spoiler = 1 if any(k in text for k in ["결말", "엔딩", "스포", "spoiler"]) else 0

                    conn.execute("""
                        INSERT OR IGNORE INTO videos (video_id, channel_id, channel_name, title,
                            description, published_at, view_count, duration_sec, has_spoiler)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        vid, channel_id, channel, title, desc,
                        sn.get("publishedAt", ""),
                        int(stats.get("viewCount", 0)),
                        dur, has_spoiler,
                    ))
                    batch_new += 1

                conn.commit()
                total_new += batch_new
                fetched += len(items)
                print(f"  +{batch_new}개 (누적 {total_new})")

                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

                time.sleep(0.2)

            except Exception as e:
                print(f"  ⚠️ {e}")
                break

    conn.close()
    print(f"\n{'='*50}")
    print(f"✅ 수집 완료: 신규 {total_new}개 (총 {len(existing) + total_new}개)")


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    print("🎬 키워드 기반 대량 수집 시작...")
    fetch_by_search(max_per_query=100)
