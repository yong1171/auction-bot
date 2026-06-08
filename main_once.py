"""
GitHub Actions에서 1회 실행되는 스크립트
매일 오전 7시 자동 실행됨
"""
import os
import json
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from anthropic import Anthropic

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

client = Anthropic(api_key=ANTHROPIC_API_KEY)


def get_kakao_access_token():
    if not KAKAO_REFRESH_TOKEN:
        print("❌ KAKAO_REFRESH_TOKEN 없음")
        return None
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": KAKAO_REST_API_KEY,
            "refresh_token": KAKAO_REFRESH_TOKEN,
        }
    )
    data = res.json()
    return data.get("access_token")


def send_kakao_message(access_token, message):
    res = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "template_object": json.dumps({
                "object_type": "text",
                "text": message,
                "link": {
                    "web_url": "https://www.courtauction.go.kr",
                    "mobile_web_url": "https://www.courtauction.go.kr"
                }
            })
        }
    )
    return res.status_code == 200


def search_auction_items():
    items = []
    queries = [
        "부산 농지 전 답 경매 진행중 2026 창원지방법원 부산지방법원 100평",
        "김해시 농지 전 답 경매 2026 창원지방법원 최저가 7000만원",
        "양산시 농지 전 답 경매 2026 창원지방법원",
        "부산 빌라 단독주택 경매 2026 부산지방법원 유찰 2억 이하",
        "김해 양산 상가주택 빌라 경매 2026 유찰",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    seen_ids = set()

    for query in queries:
        try:
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=10"
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            import re
            text = soup.get_text()
            case_numbers = re.findall(r'20\d{2}타경\d+', text)
            for case_num in case_numbers:
                if case_num not in seen_ids:
                    seen_ids.add(case_num)
                    items.append({
                        "id": case_num,
                        "address": "주소 현장확인 필요",
                        "found_at": datetime.now().isoformat(),
                    })
            time.sleep(2)
        except Exception as e:
            print(f"검색 오류: {e}")
            continue
    return items


def analyze_item(item):
    prompt = f"""
부동산 경매 전문 AI로서 아래 물건을 분석하고 JSON만 반환하세요.

사건번호: {item.get('id')}
소재지: {item.get('address')}

사용자: 부산 동래구, 건축업(목수), 체류형쉼터+스마트팜 목적, 직접시공 가능

JSON 형식:
{{
  "score": 75,
  "grade": "추천",
  "bid_normal": 5200,
  "rights_risk": "낮음",
  "shelter_possible": true,
  "summary": "요약 2줄",
  "kakao_message": "📍 신규 경매물건\\n사건: {item.get('id')}\\n주소: {item.get('address')}\\nAI점수: 75점 (추천)\\n입찰추천가: 5,200만원\\n권리위험: 낮음\\n체류형쉼터: 가능\\n\\n🔍 법원경매정보에서 확인하세요"
}}
"""
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        print(f"AI 분석 오류: {e}")
        return None


def main():
    print(f"🏗 스마트코브라 경매 자동검색 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 카카오 토큰
    access_token = get_kakao_access_token()
    if not access_token:
        print("⚠️ 카카오 토큰 없음")

    # 저장된 물건 불러오기
    saved_file = "saved_items.json"
    saved_ids = set()
    saved_items = []
    if os.path.exists(saved_file):
        with open(saved_file, "r", encoding="utf-8") as f:
            saved_items = json.load(f)
            saved_ids = {item["id"] for item in saved_items}

    # 검색
    print("📡 물건 검색 중...")
    new_items = search_auction_items()
    fresh_items = [i for i in new_items if i["id"] not in saved_ids]
    print(f"🆕 신규 물건: {len(fresh_items)}개")

    # 분석 + 카톡 발송
    for item in fresh_items:
        print(f"🤖 분석: {item['id']}")
        analysis = analyze_item(item)
        if analysis:
            item["analysis"] = analysis
            item["score"] = analysis.get("score", 0)
            if access_token:
                msg = analysis.get("kakao_message", f"신규 물건: {item['id']}")
                ok = send_kakao_message(access_token, msg)
                print(f"📱 카카오톡: {'✅ 성공' if ok else '❌ 실패'}")
        saved_items.append(item)
        time.sleep(3)

    # 완료 알림
    if access_token and fresh_items:
        send_kakao_message(
            access_token,
            f"✅ 오늘의 경매 검색 완료\n신규: {len(fresh_items)}개\n총 저장: {len(saved_items)}개\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    elif access_token:
        send_kakao_message(access_token, f"✅ 오늘의 경매 검색 완료\n신규 물건 없음\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    print("✅ 완료!")


if __name__ == "__main__":
    main()
