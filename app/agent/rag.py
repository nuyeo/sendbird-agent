"""RAG 파이프라인 및 에이전트 초기화 모듈."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools.retriever import create_retriever_tool
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter

from app.agent.tools import (
    cancel_order,
    refund_calculator,
    search_order_status,
    transfer_to_human,
)
from app.config import settings

logger = logging.getLogger(__name__)

agent_executor = None

# 세션별 대화 히스토리 저장소
chat_history_store: dict[str, InMemoryChatMessageHistory] = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """세션 ID에 해당하는 대화 히스토리를 반환합니다."""
    if session_id not in chat_history_store:
        chat_history_store[session_id] = InMemoryChatMessageHistory()
    return chat_history_store[session_id]


def initialize_rag() -> None:
    """RAG 시스템과 에이전트를 초기화합니다."""
    global agent_executor

    base_dir = Path(__file__).resolve().parent.parent.parent
    db_path = str(base_dir / "data" / "chroma_db")
    file_path = str(base_dir / "data" / "faq.txt")

    # 1. 벡터 DB 로드
    embeddings = OpenAIEmbeddings()
    db_path_obj = Path(db_path)
    if db_path_obj.exists() and any(db_path_obj.iterdir()):
        logger.info("기존 벡터 DB를 불러옵니다...")
        db = Chroma(persist_directory=db_path, embedding_function=embeddings)
    else:
        logger.info("문서를 새로 학습합니다...")
        if not Path(file_path).exists():
            logger.error("FAQ 파일을 찾을 수 없습니다: %s", file_path)
            return
        loader = TextLoader(file_path, encoding="utf-8")
        documents = loader.load()
        text_splitter = CharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        texts = text_splitter.split_documents(documents)
        db = Chroma.from_documents(texts, embeddings, persist_directory=db_path)

    # 2. Retriever 도구 생성
    retriever = db.as_retriever()
    retriever_tool = create_retriever_tool(
        retriever,
        "search_faq",
        "Use this tool to find official policies about refund, shipping, and general guidelines.",
    )

    # 3. 도구 모음
    tools = [
        retriever_tool,
        search_order_status,
        refund_calculator,
        cancel_order,
        transfer_to_human,
    ]

    # 4. LLM 설정
    llm = ChatOpenAI(model=settings.llm_model, temperature=settings.llm_temperature)

    system_prompt = """
    You are a helpful and precise Customer Support Agent for 'Sendbird Store'.

    Your Role:
    1. Answer user questions based ONLY on the information provided by the tools.
    2. Do NOT use your own outside knowledge.

    Decision Protocol (IMPORTANT):
    1. General Policy Questions: ALWAYS use 'search_faq' first.
    2. Specific Order Requests:
       - IF the Order ID is missing, ask the user for it.
       - YOU MUST FIRST use 'search_order_status' to get details.

    Tone and Logic Guidelines (CRITICAL):
    - Avoid unnecessary apologies. Do NOT say "Sorry" or "죄송합니다" if possible.
    - Logic Check for Cancellation:
      - IF status is '상품 준비 중' (Preparing) AND user asks "Can I cancel?":
        - SAY: "네, 현재 '상품 준비 중' 상태이므로 취소가 가능합니다. 취소해 드릴까요?"
      - IF status is '배송 중' (Shipping) or '배송 완료' (Delivered):
        - SAY: "죄송합니다. 현재 배송 상태에서는 취소가 불가능합니다."

    Strict Response Guidelines:
    - NEVER mention technical terms.
    - Speak naturally like a human agent.
    - Use Korean.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor_base = AgentExecutor(agent=agent, tools=tools, verbose=True)

    agent_executor = RunnableWithMessageHistory(
        agent_executor_base,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    logger.info("Agent Ready (with Memory & Handoff)")


def get_ai_response(user_query: str, user_id: str = "default") -> str:
    """사용자 쿼리에 대한 AI 응답을 생성합니다.

    Args:
        user_query: 사용자 메시지.
        user_id: 사용자 식별자 (세션 관리용).

    Returns:
        AI 응답 문자열.
    """
    if agent_executor is None:
        return "AI가 준비되지 않았습니다."

    try:
        response = agent_executor.invoke(
            {"input": user_query},
            config={"configurable": {"session_id": user_id}},
        )
        return response["output"]
    except Exception:
        logger.exception("AI 응답 생성 중 오류")
        return "죄송합니다. 잠시 후 다시 시도해 주세요."
