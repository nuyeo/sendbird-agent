import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain.tools.retriever import create_retriever_tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from dotenv import load_dotenv

# 도구들 가져오기
from app.tools import search_order_status, refund_calculator, cancel_order, transfer_to_human

load_dotenv()

agent_executor = None


def initialize_rag():
    global agent_executor

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(BASE_DIR, "data", "chroma_db")
    file_path = os.path.join(BASE_DIR, "data", "faq.txt")

    # 1. 벡터 DB 로드
    embeddings = OpenAIEmbeddings()
    if os.path.exists(db_path) and os.listdir(db_path):
        print("💾 [AI Init] 기존 벡터 DB를 불러옵니다...")
        db = Chroma(persist_directory=db_path, embedding_function=embeddings)
    else:
        print("🤖 [AI Init] 문서를 새로 학습합니다...")
        if not os.path.exists(file_path):
            print("🚨 파일을 찾을 수 없습니다.")
            return
        loader = TextLoader(file_path, encoding="utf-8")
        documents = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=0)
        texts = text_splitter.split_documents(documents)
        db = Chroma.from_documents(texts, embeddings, persist_directory=db_path)

    # 2. Retriever 도구 생성
    retriever = db.as_retriever()
    retriever_tool = create_retriever_tool(
        retriever,
        "search_faq",
        "Use this tool to find official policies about refund, shipping, and general guidelines."
    )

    # 3. 도구 모음
    tools = [retriever_tool, search_order_status, refund_calculator, cancel_order, transfer_to_human]

    # 4. LLM 설정
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    # 📌 [수정 완료] 중괄호({})를 모두 제거한 안전한 프롬프트
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
    - Avoid unnecessary apologies. Do NOT say "Sorry" or "죄송합니다" if the user's request is possible.
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

    # 5. 메모리 기능 (Session ID별로 대화 기억)
    chat_history_store = {}

    def get_session_history(session_id: str):
        if session_id not in chat_history_store:
            chat_history_store[session_id] = InMemoryChatMessageHistory()
        return chat_history_store[session_id]

    agent_executor = RunnableWithMessageHistory(
        agent_executor_base,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    print("✅ [AI Init] Agent Ready (with Memory & Handoff)")


def get_ai_response(user_query: str, user_id: str = "default") -> str:
    if agent_executor is None:
        return "AI가 준비되지 않았습니다."

    try:
        response = agent_executor.invoke(
            {"input": user_query},
            config={"configurable": {"session_id": user_id}}
        )
        return response["output"]
    except Exception as e:
        print(f"🚨 Error: {e}")
        # 에러가 나면 간단한 메시지 리턴 (서버 안 죽게)
        return "죄송합니다. 잠시 후 다시 시도해 주세요."