# 🦜 Sendbird AI Agent (RAG & Tool Calling)

Sendbird Chat API와 LangChain을 활용하여 구축한 **지능형 CS 에이전트**입니다.
단순한 규칙 기반 챗봇을 넘어, 기업 문서를 참조(RAG)하여 답변하고 실제 비즈니스 로직(Tool Calling)을 수행할 수 있도록 설계되었습니다.

## 🚀 Key Features

- **Real-time Communication**: Sendbird Webhook & API를 활용한 실시간 양방향 통신
- **RAG (Retrieval-Augmented Generation)**: LangChain과 Vector DB(Chroma)를 활용하여 PDF/TXT 문서 기반의 정확한 답변 제공
- **Prompt Engineering**: System Prompt를 활용한 페르소나 부여 및 Hallucination 제어
- **Async Processing**: FastAPI의 `BackgroundTasks`를 활용한 비동기 메시지 처리 및 성능 최적화
- **Scalable Architecture**: 기능 확장(Tool Calling)이 용이한 모듈형 구조

## 🛠 Tech Stack

- **Framework**: Python 3.11, FastAPI
- **AI & LLM**: LangChain, OpenAI (GPT-3.5/4), ChromaDB (Vector Store)
- **Infrastructure**: Ngrok (Tunneling), Docker (Planned)
- **Communication**: Sendbird Chat SDK / API

## 🏗 Architecture

```mermaid
graph LR
    User[User] -->|Send Message| Sendbird[Sendbird Platform]
    Sendbird -->|Webhook (POST)| Agent[FastAPI Agent Server]
    Agent -->|Retrieve Context| VectorDB[(Chroma DB)]
    VectorDB -->|Context| Agent
    Agent -->|Prompt + Context| LLM[OpenAI GPT]
    LLM -->|Answer| Agent
    Agent -->|Send API| Sendbird
    Sendbird -->|Reply| User
```

## ⚡️ Quick Start

### 1\. Prerequisites

  - Python 3.9+
  - Sendbird Application ID & API Token
  - OpenAI API Key

### 2\. Installation

```bash
# Clone the repository
git clone [https://github.com/YOUR_USERNAME/sendbird-ai-agent.git](https://github.com/YOUR_USERNAME/sendbird-ai-agent.git)

# Install dependencies
pip install -r requirements.txt
```

### 3\. Environment Setup

Create a `.env` file in the root directory:

```ini
SENDBIRD_APP_ID="your_app_id"
SENDBIRD_API_TOKEN="your_api_token"
OPENAI_API_KEY="sk-..."
```

### 4\. Run Server

```bash
uvicorn main:app --reload
```

## 📝 License

This project is licensed under the MIT License.

