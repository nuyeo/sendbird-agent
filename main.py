import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from app.rag import initialize_rag, get_ai_response

# 환경변수 로드
load_dotenv()

APP_ID = os.getenv("SENDBIRD_APP_ID")
API_TOKEN = os.getenv("SENDBIRD_API_TOKEN")
SENDBIRD_API_URL = f"https://api-{APP_ID}.sendbird.com/v3"


# ✅ Lifespan(수명 주기) 정의: 서버가 켜질 때와 꺼질 때 할 일을 정의함
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [시작될 때 실행]
    print("🚀 서버가 시작되었습니다. AI 모델을 로드합니다...")
    initialize_rag()

    yield  # 서버가 돌아가는 동안 대기

    # [꺼질 때 실행] (지금은 딱히 없지만 나중에 DB 연결 해제 등을 여기서 함)
    print("👋 서버가 종료됩니다. 리소스를 정리합니다.")


# ✅ FastAPI 앱 생성 시 lifespan 주입
app = FastAPI(lifespan=lifespan)


async def send_message_to_sendbird(channel_url: str, message: str):
    headers = {
        "Content-Type": "application/json; charset=utf8",
        "Api-Token": API_TOKEN
    }
    payload = {
        "message_type": "MESG",
        "user_id": "ai_agent_bot",
        "message": message
    }
    async with httpx.AsyncClient() as client:
        url = f"{SENDBIRD_API_URL}/group_channels/{channel_url}/messages"
        await client.post(url, json=payload, headers=headers)
        # print(f"✅ [Sent] {message}")


@app.post("/webhook")
async def sendbird_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    category = data.get("category")

    # 그룹 채널 메시지 이벤트만 처리
    if category == "group_channel:message_send":
        sender = data.get("sender", {})

        # 봇 자신이 보낸 메시지는 무시
        if sender.get("user_id") == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        print(f"📩 [질문] {user_message}")

        # --- AI 답변 생성 ---
        # 1. RAG 엔진에게 질문 던지기
        ai_answer = get_ai_response(user_message)
        print(f"🤖 [답변] {ai_answer}")

        # 2. Sendbird로 답장 보내기 (비동기)
        background_tasks.add_task(send_message_to_sendbird, channel_url, ai_answer)

    return {"status": "ok"}


@app.get("/")
def health_check():
    return {"status": "Server is running"}