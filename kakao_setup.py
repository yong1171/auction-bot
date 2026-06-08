"""
카카오톡 최초 토큰 발급 도우미
최초 1회만 실행하면 됩니다.
"""

import requests
import webbrowser

KAKAO_REST_API_KEY = "03ca6ba6cd8eef376d7b5c656b19338c"
REDIRECT_URI = "https://localhost"

def step1_get_auth_url():
    """1단계: 인증 URL 열기"""
    url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={KAKAO_REST_API_KEY}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    print("=" * 60)
    print("1단계: 아래 URL을 브라우저에서 열어주세요")
    print("=" * 60)
    print(url)
    print()
    print("→ 카카오 로그인 후 '허용' 클릭")
    print("→ 브라우저 주소창에 나오는 URL을 복사하세요")
    print("→ 예: https://localhost/?code=XXXXXXXXXXXXXXXX")
    print("=" * 60)
    webbrowser.open(url)

def step2_get_tokens(auth_code):
    """2단계: 인증코드로 토큰 발급"""
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": KAKAO_REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": auth_code,
        }
    )
    data = res.json()
    
    if "access_token" in data:
        print("\n✅ 토큰 발급 성공!")
        print(f"액세스 토큰: {data['access_token']}")
        print(f"리프레시 토큰: {data['refresh_token']}")
        print()
        print("=" * 60)
        print("Render.com 환경변수에 아래 값을 추가하세요:")
        print("=" * 60)
        print(f"KAKAO_REFRESH_TOKEN = {data['refresh_token']}")
        
        # 파일로도 저장
        with open("tokens.txt", "w") as f:
            f.write(f"KAKAO_ACCESS_TOKEN={data['access_token']}\n")
            f.write(f"KAKAO_REFRESH_TOKEN={data['refresh_token']}\n")
        print("\n tokens.txt 파일에도 저장됨")
        return data
    else:
        print(f"❌ 오류: {data}")
        return None

def step3_test_message(access_token):
    """3단계: 테스트 메시지 발송"""
    import json
    res = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={
            "template_object": json.dumps({
                "object_type": "text",
                "text": "✅ 스마트코브라 경매 알림 연동 완료!\n\n매일 오전 7시에 부산·김해·양산 경매 물건을 검색해서 알림을 보내드립니다. 🏗",
                "link": {
                    "web_url": "https://www.courtauction.go.kr",
                    "mobile_web_url": "https://www.courtauction.go.kr"
                }
            })
        }
    )
    if res.status_code == 200:
        print("✅ 테스트 카카오톡 발송 성공! 카톡 확인하세요.")
    else:
        print(f"❌ 발송 실패: {res.text}")

if __name__ == "__main__":
    print("🏗 카카오톡 연동 설정 도우미")
    print()
    
    step1_get_auth_url()
    
    print()
    auth_code = input("브라우저 주소창의 code= 뒤 값을 붙여넣으세요: ").strip()
    
    if auth_code:
        tokens = step2_get_tokens(auth_code)
        if tokens:
            test = input("\n테스트 카카오톡 발송할까요? (y/n): ")
            if test.lower() == "y":
                step3_test_message(tokens["access_token"])
