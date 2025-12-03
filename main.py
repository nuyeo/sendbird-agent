"""Main FastAPI application for Sendbird AI Agent."""
import os
import httpx
import time
import uuid
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any, List
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from app.rag import initialize_rag, get_ai_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

APP_ID = os.getenv("SENDBIRD_APP_ID")
API_TOKEN = os.getenv("SENDBIRD_API_TOKEN")
SENDBIRD_API_URL = f"https://api-{APP_ID}.sendbird.com/v3"

# In-memory chat logs storage
chat_logs: List[Dict[str, Any]] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting server and initializing AI agent...")
    try:
        initialize_rag()
        logger.info("✅ AI agent initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize AI agent: {e}")
        raise
    yield
    logger.info("👋 Shutting down server...")


app = FastAPI(
    title="Sendbird AI Agent",
    description="Real-time AI customer support agent",
    version="1.0.0",
    lifespan=lifespan
)

# ✅ CORS 설정 (Next.js 3000번 포트에서 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def send_message_to_sendbird(channel_url: str, message: str) -> None:
    """
    Send AI response message to Sendbird channel.

    Args:
        channel_url: Sendbird channel URL
        message: Message content to send
    """
    headers = {
        "Content-Type": "application/json; charset=utf8",
        "Api-Token": API_TOKEN
    }
    payload = {
        "message_type": "MESG",
        "user_id": "ai_agent_bot",
        "message": message
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{SENDBIRD_API_URL}/group_channels/{channel_url}/messages"
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.debug(f"Message sent to channel {channel_url}")
    except httpx.HTTPError as e:
        logger.error(f"Failed to send message to Sendbird: {e}")


@app.post("/webhook")
async def sendbird_webhook(
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Handle Sendbird webhook events for incoming messages.

    Args:
        request: FastAPI request object
        background_tasks: Background task manager

    Returns:
        Status response dictionary
    """
    data = await request.json()
    category = data.get("category")

    if category == "group_channel:message_send":
        sender = data.get("sender", {})
        user_id = sender.get("user_id", "Unknown")

        # Ignore bot's own messages
        if user_id == "ai_agent_bot":
            return {"status": "ok"}

        payload = data.get("payload", {})
        user_message = payload.get("message", "")
        channel_url = data.get("channel", {}).get("channel_url")

        logger.info(f"📩 Received message from {user_id}: {user_message[:50]}...")

        # Measure AI response time
        start_time = time.time()

        try:
            # Generate AI response with user context
            ai_answer = get_ai_response(user_message, user_id=user_id)
            duration = round((time.time() - start_time) * 1000)

            logger.info(f"🤖 Generated response in {duration}ms")

            # Store conversation log
            log_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": user_id,
                "question": user_message,
                "answer": ai_answer,
                "duration": duration,
                "feedback": None
            }
            chat_logs.insert(0, log_entry)

            # Send response asynchronously
            background_tasks.add_task(
                send_message_to_sendbird,
                channel_url,
                ai_answer
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    return {"status": "ok"}

class FeedbackRequest(BaseModel):
    """Request model for feedback."""
    feedback: str = Field(..., description="Feedback type: 'up' or 'down'")


@app.put("/api/logs/{log_id}/feedback")
def update_feedback(log_id: str, request: FeedbackRequest) -> Dict[str, Any]:
    """
    Update feedback for a specific conversation log.

    Args:
        log_id: UUID of the log entry
        request: Feedback request

    Returns:
        Success response or error
    """
    for log in chat_logs:
        if log["id"] == log_id:
            log["feedback"] = request.feedback
            logger.info(f"Feedback '{request.feedback}' added to log {log_id}")
            return {"status": "success", "log_id": log_id, "feedback": request.feedback}

    logger.warning(f"Log not found: {log_id}")
    raise HTTPException(status_code=404, detail="Log not found")


@app.get("/api/logs")
def get_chat_logs() -> Dict[str, Any]:
    """
    Retrieve all conversation logs.

    Returns:
        Dictionary containing logs list and total count
    """
    return {"logs": chat_logs, "total": len(chat_logs)}


@app.get("/")
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "Server is running", "version": "1.0.0"}