import os
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

# 환경변수 로드 (.env 파일에서 읽어옴)
load_dotenv()

APP_ID = os.getenv("SENDBIRD_APP_ID")
API_TOKEN = os.getenv("SENDBIRD_API_TOKEN")
# Sendbird API 기본 주소 구성
SENDBIRD_API_URL = f"https://api-{APP_ID}.sendbird.com/v3"

app = FastAPI()


async def send_message_to_sendbird(channel_url: str, message: str):
    """
    Sendbird 채팅방으로 메시지를 쏘는 함수 (비동기)
    """
    headers = {
        "Content-Type": "application/json; charset=utf8",
        "Api-Token": API_TOKEN
    }
    payload = {
        "message_type": "MESG",
        "user_id": "ai_agent_bot",  # 봇이 말하는 것으로 처리
        "message": message
    }

    async with httpx.AsyncClient() as client:
        url = f"{SENDBIRD_API_URL}/group_channels/{channel_url}/messages"
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ [봇 답장 성공] {message}")
        else:
            print(f"❌ [전송 실패] {response.text}")


@app.post("/webhook")
async def sendbird_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Sendbird에서 알림(Webhook)을 받는 곳
    """
    data = await request.json()

    # 1. 어떤 종류의 알림인지 확인
    category = data.get("category")

    # 2. 유저가 메시지를 보냈을 때만 반응 (group_channel:message_send)
    if category == "group_channel:message_send":
        sender = data.get("sender", {})

        # 중요: 봇 자신이 보낸 메시지면 무시 (안 그러면 무한 루프에 빠짐)
        if sender.get("user_id") == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        print(f"📩 [유저 메시지 수신] {user_message}")

        # --- 여기가 나중에 AI가 들어갈 자리입니다 ---
        # 지금은 "메아리" 봇입니다.
        reply_text = f"봇 서버가 확인했습니다: {user_message}"

        # 3. 답장 보내기 (비동기 처리)
        background_tasks.add_task(send_message_to_sendbird, channel_url, reply_text)

    return {"status": "ok"}


@app.get("/")
def health_check():
    return {"status": "Server is running"}