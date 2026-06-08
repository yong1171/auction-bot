import os
import json
import time
import schedule
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from anthropic import Anthropic

# ============================================================
# 설정
# ============================================================
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "03ca6ba6cd8eef376d7b5c656b19338c")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# 검색 조건
SEARCH_CONFIG = {
    "regions": ["부산", "김해시", "양산시"],
    "farmland": {
        "types": ["전", "답", "임야"],
        "min_area": 100,
        "max_area": 200,
        "max_price": 7000,
        "min_fail": 1,
    },
    "building": {
        "types": ["빌라", "다세대", "단독주택", "다가구", "상가주택", "근린상가"],
        "max_price": 20000,
        "min_fail": 1,
    },
    "base_location": "부산 동래구",  # 거리 기준점
}

# ============================================================
# 카카오톡 토큰 관리
# ============================================================
def get_kakao_access_token():
    """리프레시 토큰으로 액세스 토큰 갱신"""
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
    """나에게 카카오톡 메시지 보내기"""
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


# ============================================================
# 경매 물건 검색
# ============================================================
def search_auction_items():
    """구글 검색으로 경매 물건 수집"""
    items = []
    
    queries = [
        "부산 농지 전 답 경매 진행중 2026 창원지방법원 부산지방법원 최저가",
        "김해시 농지 전 답 경매 2026 창원지방법원 100평 이상",
        "양산시 농지 전 답 경매 2026 창원지방법원",
        "부산 빌라 단독주택 경매 2026 부산지방법원 유찰 최저가 2억 이하",
        "김해 양산 상가주택 빌라 경매 2026 진행중 유찰",
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
            
            # 구글 검색결과에서 사건번호 패턴 추출
            import re
            text = soup.get_text()
            
            # 사건번호 패턴: 2024타경1234, 2025타경5678
            case_numbers = re.findall(r'20\d{2}타경\d+', text)
            
            for case_num in case_numbers:
                if case_num not in seen_ids:
                    seen_ids.add(case_num)
                    # 주소 추출 시도
                    addr_match = re.search(
                        rf'{case_num}[^\n]*\n([^\n]*(?:부산|김해|양산)[^\n]*)', 
                        text
                    )
                    addr = addr_match.group(1).strip() if addr_match else "주소 확인 필요"
                    
                    items.append({
                        "id": case_num,
                        "address": addr,
                        "source": "google_search",
                        "found_at": datetime.now().isoformat(),
                    })
            
            time.sleep(2)  # 요청 간격
            
        except Exception as e:
            print(f"검색 오류: {e}")
            continue
    
    return items


# ============================================================
# AI 분석
# ============================================================
def analyze_item_with_ai(item):
    """Claude AI로 경매 물건 분석"""
    prompt = f"""
당신은 대한민국 부동산 경매 전문 AI입니다.
아래 경매 물건을 분석하고 JSON만 반환하세요.

물건정보:
- 사건번호: {item.get('id')}
- 소재지: {item.get('address')}
- 추가정보: {item.get('extra', '없음')}

사용자 정보:
- 부산 동래구 거주, 건축업(목수) 전문가
- 방수기능사, 굴삭기기능사 보유, 건축기사 준비중
- 농지: 체류형쉼터+스마트팜 타운 조성 목적
- 주거/상가: 낙찰 후 직접수리 → 단기매도 목적
- 직접시공 가능 (수리비 절감 강점)

분석 후 아래 JSON 형식으로만 반환 (다른 텍스트 없이):
{{
  "score": 75,
  "grade": "추천",
  "type": "farmland",
  "bid_conservative": 4500,
  "bid_normal": 5200,
  "bid_aggressive": 5800,
  "rights_risk": "낮음",
  "rights_inherit": "없음",
  "shelter_possible": true,
  "shelter_reason": "비진흥구역 추정, 현장확인 필요",
  "repair_direct": 0,
  "repair_outsource": 0,
  "net_profit": 2000,
  "structure_risk": "낮음",
  "summary": "2줄 요약",
  "checklist": ["체크항목1", "체크항목2", "체크항목3"],
  "kakao_message": "📍 신규 경매물건\\n사건: {item.get('id')}\\n주소: {item.get('address')}\\nAI점수: 75점 (추천)\\n입찰추천가: 5,200만원\\n권리위험: 낮음\\n체류형쉼터: 가능\\n\\n▶ 자세히 보기"
}}
"""
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        print(f"AI 분석 오류: {e}")
        return None


# ============================================================
# 메인 작업 (매일 오전 7시 실행)
# ============================================================
def daily_job():
    print(f"\n{'='*50}")
    print(f"🔍 경매 자동검색 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    # 1. 저장된 물건 불러오기
    saved_file = "saved_items.json"
    saved_ids = set()
    saved_items = []
    
    if os.path.exists(saved_file):
        with open(saved_file, "r", encoding="utf-8") as f:
            saved_items = json.load(f)
            saved_ids = {item["id"] for item in saved_items}
    
    # 2. 새 물건 검색
    print("📡 물건 검색 중...")
    new_items = search_auction_items()
    print(f"✅ {len(new_items)}개 물건 발견")
    
    # 3. 신규 물건만 필터링
    fresh_items = [i for i in new_items if i["id"] not in saved_ids]
    print(f"🆕 신규 물건: {len(fresh_items)}개")
    
    # 4. 카카오 토큰 발급
    access_token = get_kakao_access_token()
    if not access_token:
        print("⚠️ 카카오 토큰 없음 - 알림 스킵")
    
    # 5. 신규 물건 AI 분석 + 카카오톡 발송
    for item in fresh_items:
        print(f"\n🤖 분석 중: {item['id']}")
        analysis = analyze_item_with_ai(item)
        
        if analysis:
            item["analysis"] = analysis
            item["score"] = analysis.get("score", 0)
            
            # 카카오톡 발송
            if access_token:
                msg = analysis.get("kakao_message", f"신규 물건: {item['id']}")
                success = send_kakao_message(access_token, msg)
                print(f"📱 카카오톡: {'✅ 발송완료' if success else '❌ 발송실패'}")
        
        saved_items.append(item)
        time.sleep(3)  # API 과부하 방지
    
    # 6. 매각기일 3일 전 재분석
    print("\n🔄 매각기일 임박 물건 재분석...")
    three_days_later = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    for item in saved_items:
        next_date = item.get("next_date", "")
        if next_date and next_date <= three_days_later and item.get("analysis"):
            print(f"⏰ 재분석: {item['id']} (매각기일: {next_date})")
            analysis = analyze_item_with_ai(item)
            if analysis and access_token:
                msg = f"⏰ 매각기일 임박 재분석\n{analysis.get('kakao_message', '')}"
                send_kakao_message(access_token, msg)
            time.sleep(3)
    
    # 7. 저장
    with open(saved_file, "w", encoding="utf-8") as f:
        json.dump(saved_items, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 완료! 총 저장 물건: {len(saved_items)}개")
    
    # 8. 완료 알림
    if access_token:
        summary = f"✅ 오늘의 경매 검색 완료\n신규: {len(fresh_items)}개\n총 저장: {len(saved_items)}개\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        send_kakao_message(access_token, summary)


# ============================================================
# 카카오 토큰 초기 발급 (최초 1회)
# ============================================================
def get_initial_token(auth_code):
    """인증코드로 최초 토큰 발급"""
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": KAKAO_REST_API_KEY,
            "redirect_uri": "https://localhost",
            "code": auth_code,
        }
    )
    data = res.json()
    print("액세스 토큰:", data.get("access_token"))
    print("리프레시 토큰:", data.get("refresh_token"))
    return data


# ============================================================
# 서버 실행
# ============================================================
if __name__ == "__main__":
    print("🏗 스마트코브라 경매 자동 분석 시스템 시작")
    print(f"⏰ 매일 오전 7시 자동 실행 예약됨")
    
    # 매일 오전 7시 실행
    schedule.every().day.at("07:00").do(daily_job)
    
    # 시작 시 즉시 1회 실행 (테스트용, 필요시 주석처리)
    # daily_job()
    
    print("✅ 대기 중... (Ctrl+C로 종료)")
    while True:
        schedule.run_pending()
        time.sleep(60)
