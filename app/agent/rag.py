"""RAG 파이프라인 및 에이전트 초기화 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools.retriever import create_retriever_tool
from langchain_community.callbacks import get_openai_callback
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_community.document_loaders import TextLoader
from langchain_core.messages import BaseMessage
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


class _TrimmedRedisChatMessageHistory(RedisChatMessageHistory):
    """최신 N개 메시지로 히스토리를 제한해 토큰 선형 증가를 방지합니다.

    Redis에는 전체 이력을 보존하고, LLM에게 전달하는 messages 프로퍼티에서만
    트리밍을 적용합니다. 이렇게 하면 로그 감사용 전체 이력과 LLM 컨텍스트 제한을
    독립적으로 관리할 수 있습니다.
    """

    def __init__(self, session_id: str, url: str, ttl: int, max_messages: int) -> None:
        """초기화합니다.

        Args:
            session_id: Redis 키에 사용할 세션 식별자.
            url: Redis 연결 URL.
            ttl: 세션 TTL (초).
            max_messages: LLM에 전달할 최대 메시지 수 (human + ai 합산).
        """
        super().__init__(session_id=session_id, url=url, ttl=ttl)
        self._max_messages = max_messages

    @property
    def messages(self) -> list[BaseMessage]:
        """최신 max_messages 개의 메시지만 반환합니다."""
        all_msgs = super().messages
        if len(all_msgs) > self._max_messages:
            return all_msgs[-self._max_messages :]
        return all_msgs


def get_session_history(session_id: str) -> _TrimmedRedisChatMessageHistory:
    """세션 ID에 해당하는 Redis 기반 대화 히스토리를 반환합니다.

    Args:
        session_id: 사용자 식별자.

    Returns:
        히스토리 트리밍이 적용된 RedisChatMessageHistory 인스턴스.
    """
    return _TrimmedRedisChatMessageHistory(
        session_id=session_id,
        url=settings.redis_url,
        ttl=settings.session_ttl_seconds,
        max_messages=settings.history_max_messages,
    )


def _get_postgres_connection_string() -> str:
    """PGVector용 SQLAlchemy 연결 문자열을 반환합니다.

    langchain-postgres는 psycopg(v3) 드라이버를 사용하므로 settings.postgres_url
    (postgresql+psycopg://...)을 그대로 사용합니다.
    """
    return settings.postgres_url


async def initialize_rag() -> None:
    """RAG 시스템과 에이전트를 초기화합니다.

    PGVector는 async_mode=True로 생성한다. 에이전트가 ainvoke 경로로 호출되면
    내부적으로 asimilarity_search가 실행되는데, sync 모드의 PGVector는 async
    엔진이 없어 AssertionError로 실패하기 때문이다. 초기 인덱싱 체크/적재 또한
    같은 인스턴스에서 await 호출로 수행한다.
    """
    global agent_executor, agent_executor_base

    base_dir = Path(__file__).resolve().parent.parent.parent
    file_path = str(base_dir / "data" / "faq.txt")

    # 1. 임베딩 & pgvector 벡터 DB (async 모드)
    embeddings = OpenAIEmbeddings()
    connection_string = _get_postgres_connection_string()

    db = PGVector(
        embeddings=embeddings,
        collection_name=_VECTOR_COLLECTION,
        connection=connection_string,
        use_jsonb=True,
        async_mode=True,
    )

    # 벡터 DB가 비어 있으면 FAQ 문서를 인덱싱
    existing = await db.asimilarity_search("test", k=1)
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
        await db.aadd_documents(texts)
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
    # timeout/max_retries를 명시해 RateLimit/일시 네트워크 오류에서 호출이 즉시
    # 실패하지 않도록 한다. LangChain ChatOpenAI는 내부적으로 OpenAI SDK의 retry를
    # 활용해 지수 백오프를 수행한다.
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

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

    토큰 사용량은 langchain_community.callbacks.get_openai_callback로 수집한다.
    이 컨텍스트 매니저는 contextvars 기반이라 async 흐름에서도 정상 동작한다.

    Args:
        user_query: 사용자 메시지.
        session_id: LLM 대화 메모리 키. WebSocket 연결마다 발급되어,
            새 탭/새로고침 시 새 대화로 시작되도록 한다. user_id와 분리되어
            영속 로그(chat_logs)는 user_id로, LLM 컨텍스트는 session_id로 관리.

    Returns:
        {"output": str, "token_usage": dict | None, "error": bool} 형태의
        딕셔너리. token_usage는 prompt/completion/total tokens를 포함하며,
        사용량 집계가 실패한 경우 None. error는 LLM 호출이 실패했거나 에이전트가
        초기화되지 않아 fallback 메시지를 반환한 경우 True가 된다 — 호출자가
        성공/실패 카운터를 분리할 때 사용한다.
    """
    if agent_executor is None:
        return {
            "output": "AI가 준비되지 않았습니다.",
            "token_usage": None,
            "error": True,
        }

    try:
        with get_openai_callback() as cb:
            response = await agent_executor.ainvoke(
                {"input": user_query},
                config={"configurable": {"session_id": session_id}},
            )
        token_usage = (
            {
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
                "total_tokens": cb.total_tokens,
            }
            if cb.total_tokens > 0
            else None
        )
        return {"output": response["output"], "token_usage": token_usage, "error": False}
    except Exception:
        logger.exception("AI 응답 생성 중 오류")
        return {
            "output": "죄송합니다. 잠시 후 다시 시도해 주세요.",
            "token_usage": None,
            "error": True,
        }
