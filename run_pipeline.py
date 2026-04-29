#!/usr/bin/env python3
"""전체 파이프라인 실행"""
import sys, warnings
warnings.filterwarnings("ignore")

from config import YOUTUBE_API_KEY, ANTHROPIC_API_KEY, TMDB_API_KEY

def check_keys():
    missing = []
    if not YOUTUBE_API_KEY: missing.append("YOUTUBE_API_KEY")
    if not ANTHROPIC_API_KEY: missing.append("ANTHROPIC_API_KEY")
    if not TMDB_API_KEY: missing.append("TMDB_API_KEY")
    if missing:
        print(f"❌ 환경변수가 설정되지 않았습니다: {', '.join(missing)}")
        print("\n설정 방법:")
        for k in missing:
            print(f"  export {k}=\"your_key_here\"")
        sys.exit(1)

def main():
    check_keys()
    print("=" * 50)
    print("🎬 영화 큐레이션 파이프라인 시작")
    print("=" * 50)

    # Step 1: 영상 수집
    print("\n📥 Step 1: YouTube 영상 수집")
    print("-" * 40)
    from fetch_videos import fetch_all
    fetch_all()

    # Step 2: AI 매칭
    print("\n🎯 Step 2: AI 영화 매칭")
    print("-" * 40)
    from match_movies import match_all
    match_all()

    # Step 3: 메타데이터 보강
    print("\n📚 Step 3: TMDB 메타데이터 보강")
    print("-" * 40)
    from enrich import enrich_all
    enrich_all()

    # Step 4: 피드 생성
    print("\n📤 Step 4: JSON 피드 생성")
    print("-" * 40)
    from export import export_feed
    export_feed()

    print("\n" + "=" * 50)
    print("✅ 파이프라인 완료!")
    print("=" * 50)

if __name__ == "__main__":
    main()
