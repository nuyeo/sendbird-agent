import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain.chains import RetrievalQA
from dotenv import load_dotenv

load_dotenv()

# 전역 변수
qa_chain = None


def initialize_rag():
    """
    서버 시작 시 실행: data/faq.txt를 읽어 학습
    """
    global qa_chain

    # 📌 [수정 포인트 1] 경로 설정 로직 추가
    # 현재 파일(app/rag.py)의 부모(app)의 부모(root)를 찾음
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # data/faq.txt 경로 완성
    file_path = os.path.join(BASE_DIR, "data", "faq.txt")

    # 벡터 DB 저장 경로 (data/chroma_db 폴더에 저장)
    db_path = os.path.join(BASE_DIR, "data", "chroma_db")

    if os.path.exists(db_path) and os.listdir(db_path):
        print("💾 [AI Init] 기존 벡터 DB를 불러옵니다... (비용 절약)")
        embeddings = OpenAIEmbeddings()
        db = Chroma(persist_directory=db_path, embedding_function=embeddings)
    else:
        print(f"🤖 [AI Init] 문서를 새로 학습합니다... (API 호출)")
        print(f"🤖 [AI Init] 다음 문서를 학습합니다: {file_path}")

        # 1. 문서 로드 (경로 수정됨)
        if not os.path.exists(file_path):
            print(f"🚨 [Error] 파일을 찾을 수 없습니다: {file_path}")
            return

        loader = TextLoader(file_path, encoding="utf-8")
        documents = loader.load()

        # 2. 문서 쪼개기
        text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=0)
        texts = text_splitter.split_documents(documents)

        # 3. 임베딩 & 벡터 DB 생성 (경로 수정됨)
        embeddings = OpenAIEmbeddings()

        # persist_directory를 지정하면 DB 파일이 data/chroma_db에 예쁘게 저장됩니다.
        db = Chroma.from_documents(texts, embeddings, persist_directory=db_path)

    # 4. 검색기 생성
    retriever = db.as_retriever(search_kwargs={"k": 2})

    # 5. LLM 설정
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

    # 6. Chain 생성
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever
    )
    print("✅ [AI Init] 학습 완료! AI가 준비되었습니다.")


def get_ai_response(user_query: str) -> str:
    if qa_chain is None:
        return "죄송합니다. AI가 아직 준비되지 않았습니다."

    response = qa_chain.invoke(user_query)
    return response['result']