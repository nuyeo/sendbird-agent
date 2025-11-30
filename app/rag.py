import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain.tools.retriever import create_retriever_tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
# from langchain import hub  <-- 이거 대신 직접 만듭니다
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv

# 도구들 가져오기
from app.tools import search_order_status, refund_calculator

load_dotenv()

agent_executor = None


def initialize_rag():
    global agent_executor

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(BASE_DIR, "data", "chroma_db")
    file_path = os.path.join(BASE_DIR, "data", "faq.txt")

    # 1. 벡터 DB 로드 (기존과 동일)
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

    # 2. Retriever 도구 생성 (설명 구체화)
    retriever = db.as_retriever()
    retriever_tool = create_retriever_tool(
        retriever,
        "search_faq",
        "Use this tool to find official policies about refund, shipping, and general guidelines."
    )

    # 3. 도구 모음
    tools = [retriever_tool, search_order_status, refund_calculator]

    # 4. LLM 설정
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    # 📌 [핵심] 프롬프트 엔지니어링 (Hallucination 제어 & 출처 표기)
    # 시스템 프롬프트에 '페르소나'와 '제약조건'을 강력하게 겁니다.
    system_prompt = """
    You are a helpful and precise Customer Support Agent for 'Sendbird Store'.

    Your Role:
    1. Answer user questions based ONLY on the information provided by the tools (FAQ, Order Search, Refund Calculator).
    2. Do NOT use your own outside knowledge. If the user asks about general topics (e.g., "Who is Napoleon?", "Weather in Seoul"), politely refuse and say you can only help with store-related inquiries.

    Strict Guidelines:
    - If the information is NOT found in the tools, explicitly say: "죄송합니다. 해당 내용은 제가 알 수 없는 정보입니다. 고객센터로 문의 부탁드립니다."
    - Do NOT make up facts (Hallucination).
    - When using the 'search_faq' tool, always mention the source section if possible (e.g., "규정 2조에 따르면...").

    Tone:
    - Be polite, professional, and concise.
    - Use Korean.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),  # 도구 사용 내역이 들어가는 자리
    ])

    # 5. Agent 생성
    agent = create_tool_calling_agent(llm, tools, prompt)

    # 6. 실행기 생성
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print("✅ [AI Init] Agent가 준비되었습니다. (Custom Prompt Applied)")


def get_ai_response(user_query: str) -> str:
    if agent_executor is None:
        return "AI가 준비되지 않았습니다."

    try:
        response = agent_executor.invoke({"input": user_query})
        return response["output"]
    except Exception as e:
        print(f"🚨 Error: {e}")
        return "죄송합니다. 처리 중 오류가 발생했습니다."