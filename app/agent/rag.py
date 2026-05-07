"""RAG 파이프라인 및 에이전트 초기화 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools.retriever import create_retriever_tool
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_community.document_loaders import TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import CharacterTextSplitter

from app.agent.tools import (
    cancel_order,
    refund_calculator,
    search_order_status,
    transfer_to_human,
)
from app.config import settings
from app.observability.logger import get_logger
from app.prompt.loader import load_prompt

logger = get_logger()

agent_executor: RunnableWithMessageHistory | None = None
agent_executor_base: AgentExecutor | None = None

_VECTOR_COLLECTION = "faq"


def get_session_history(session_id: str) -> RedisChatMessageHistory:
    """세션 ID에 해당하는 Redis 기반 대화 히스토리를 반환합니다.

    Args:
        session_id: 사용자 식별자.

    Returns:
        RedisChatMessageHistory 인스턴스.
    """
    return RedisChatMessageHistory(
        session_id=session_id,
        url=settings.redis_url,
        ttl=settings.session_ttl_seconds,
    )


def _get_postgres_connection_string() -> str:
    """PGVector용 SQLAlchemy 연결 문자열을 반환합니다.

    langchain-postgres는 psycopg(v3) 드라이버를 사용하므로 settings.postgres_url
    (postgresql+psycopg://...)을 그대로 사용합니다.
    """
    return settings.postgres_url


def initialize_rag() -> None:
    """RAG 시스템과 에이전트를 초기화합니다."""
    global agent_executor, agent_executor_base

    base_dir = Path(__file__).resolve().parent.parent.parent
    file_path = str(base_dir / "data" / "faq.txt")

    # 1. 임베딩 & pgvector 벡터 DB
    embeddings = OpenAIEmbeddings()
    connection_string = _get_postgres_connection_string()

    db = PGVector(
        embeddings=embeddings,
        collection_name=_VECTOR_COLLECTION,
        connection=connection_string,
        use_jsonb=True,
    )

    # 벡터 DB가 비어 있으면 FAQ 문서를 인덱싱
    existing = db.similarity_search("test", k=1)
    if not existing:
        logger.info("FAQ 문서를 pgvector에 최초 인덱싱합니다...")
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
        db.add_documents(texts)
        logger.info("FAQ 인덱싱 완료: %d 청크", len(texts))
    else:
        logger.info("기존 pgvector 벡터 DB를 불러옵니다...")

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

    # 5. 프롬프트 로드 (YAML 외부 파일)
    prompt_config = load_prompt("cs_agent_v1")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt_config.system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor_base = AgentExecutor(agent=agent, tools=tools, verbose=True)

    agent_executor = RunnableWithMessageHistory(
        agent_executor_base,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    logger.info("Agent Ready (Redis 세션 + pgvector RAG)")


async def get_ai_response(user_query: str, session_id: str) -> dict[str, Any]:
    """사용자 쿼리에 대한 AI 응답을 생성합니다.

    도구(search_order_status 등)가 async로 정의되어 있으므로 agent_executor도
    async 경로(ainvoke)로 호출해야 한다. 동일 이벤트 루프에서 LLM/DB 호출을
    함께 처리하므로 별도 thread offload는 불필요하다.

    Args:
        user_query: 사용자 메시지.
        session_id: LLM 대화 메모리 키. WebSocket 연결마다 발급되어,
            새 탭/새로고침 시 새 대화로 시작되도록 한다. user_id와 분리되어
            영속 로그(chat_logs)는 user_id로, LLM 컨텍스트는 session_id로 관리.

    Returns:
        {"output": str, "token_usage": dict | None} 형태의 딕셔너리.
    """
    if agent_executor is None:
        return {"output": "AI가 준비되지 않았습니다.", "token_usage": None}

    try:
        response = await agent_executor.ainvoke(
            {"input": user_query},
            config={"configurable": {"session_id": session_id}},
        )
        return {"output": response["output"], "token_usage": None}
    except Exception:
        logger.exception("AI 응답 생성 중 오류")
        return {"output": "죄송합니다. 잠시 후 다시 시도해 주세요.", "token_usage": None}
