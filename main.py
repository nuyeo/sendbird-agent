import os
import httpx
import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from app.rag import initialize_rag, get_ai_response

# 환경변수 로드
load_dotenv()

APP_ID = os.getenv("SENDBIRD_APP_ID")
API_TOKEN = os.getenv("SENDBIRD_API_TOKEN")
SENDBIRD_API_URL = f"https://api-{APP_ID}.sendbird.com/v3"

# 📌 대시보드에 보여줄 로그 저장소 (In-Memory)
chat_logs = []


# ✅ Lifespan: 서버 시작 시 AI 로딩
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 서버가 시작되었습니다. AI 모델을 로드합니다...")
    initialize_rag()
    yield
    print("👋 서버가 종료됩니다.")


app = FastAPI(lifespan=lifespan)

# ✅ CORS 설정 (Next.js 3000번 포트에서 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/webhook")
async def sendbird_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    category = data.get("category")

    if category == "group_channel:message_send":
        sender = data.get("sender", {})

        # 봇 자신이 보낸 메시지면 무시
        if sender.get("user_id") == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        # user_id를 추출해서 AI에게 전달 (메모리 기능용)
        user_id = sender.get("user_id", "Unknown")

        print(f"📩 [질문] {user_message} (User: {user_id})")

        # ⏱️ 시간 측정
        start_time = time.time()

        # 1. AI 답변 생성 (user_id를 함께 넘겨줘야 기억 가능)
        ai_answer = get_ai_response(user_message, user_id=user_id)

        duration = round((time.time() - start_time) * 1000)
        print(f"🤖 [답변] {ai_answer}")

        # 2. 로그 저장 (ID 및 피드백용 필드 포함)
        log_id = str(uuid.uuid4())
        log_entry = {
            "id": log_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id,
            "question": user_message,
            "answer": ai_answer,
            "duration": duration,
            "feedback": None
        }
        chat_logs.insert(0, log_entry)

        # 3. Sendbird 답장 전송
        background_tasks.add_task(send_message_to_sendbird, channel_url, ai_answer)

    return {"status": "ok"}

class FeedbackRequest(BaseModel):
    feedback: str # "up" or "down"

@app.put("/api/logs/{log_id}/feedback")
def update_feedback(log_id: str, request: FeedbackRequest):
    """
    특정 로그에 좋아요(up)/싫어요(down) 피드백을 저장함
    """
    for log in chat_logs:
        if log["id"] == log_id:
            log["feedback"] = request.feedback
            return {"status": "success", "log_id": log_id, "feedback": request.feedback}
    return {"error": "Log not found"}

# ✅ 대시보드가 데이터를 가져갈 API
@app.get("/api/logs")
def get_chat_logs():
    return {"logs": chat_logs}


@app.get("/")
def health_check():
    return {"status": "Server is running"}