# K-Lingo AI Server: 고성능 Multi-Agent 한국어 튜터링 서버

> **"Fine-tuned LLM과 Multi-Agent가 만드는 초개인화 한국어 교육 시스템"**

K-Lingo는 단순한 채팅을 넘어, **LangGraph 기반의 에이전트 오케스트레이션**과 **vLLM 기반의 고속 추론 엔진**을 결합한 지능형 백엔드 서버입니다.
범용 LLM의 한계를 극복하기 위해 한국어 교육 데이터로 **Fine-tuning된 모델**(LoRA)을 탑재하여, 학습자의 발화를 교육학적 관점(세종학당 기준)에서 정밀하게 진단하고 교정합니다.

상세 내용 PPT : https://www.canva.com/design/DAG891OKYco/9KLsWyNkmYsfuIo2YeLTog/edit

---

## 🏗️ System Architecture

이 프로젝트는 **FastAPI**와 **LangGraph**를 중심으로 비즈니스 로직을 처리하며, 무거운 추론 작업은 **vLLM**이 탑재된 별도의 Inference Server로 오프로딩하여 높은 처리량(Throughput)을 보장합니다.

### 1. High-Level Architecture

사용자 요청은 API Gateway를 통해 전달되며, Supervisor Agent가 문맥에 따라 **RAG(검색)** 또는 **Fine-tuned Model(추론)** 파이프라인으로 라우팅합니다.

```ascii
                                    [Client / Front-end]
                                            ⬇️
                               [ FastAPI (Async Gateway) ]
                                            ⬇️
+-------------------------+      +--------------------------+      +-----------------------+
|   Agent Orchestrator    | <--> |      Model Serving       | <--> |    Knowledge Base     |
| (LangGraph Supervisor)  |      |   (vLLM / Triton IS)     |      |   (Vector DB / RAG)   |
+-------------------------+      +--------------------------+      +-----------------------+
            ⬇️                                ⬇️
    +----------------+           +-----------------------------+
    |  Context Mgmt  |           |      Fine-tuned LLM         |
    | (Redis/SQL DB) |           | (LoRA Adapted for Education)|
    +----------------+           +-----------------------------+

```

### 2. Multi-Agent & Serving Workflow

복합적인 평가 업무를 처리하기 위해 'Supervisor'가 하위 에이전트들을 제어하며, 각 에이전트는 vLLM 엔드포인트를 호출하여 최소한의 지연시간(Latency)으로 분석 결과를 생성합니다.

```ascii
                     [ User Input ]
                           ⬇️
                 +-------------------+
                 |  Supervisor Agent |  <-- (Router & State Manager)
                 +-------------------+
                           ⬇️
        +-----------------------------------------+
        |         Parallel Execution (Async)      |
        +-----------------------------------------+
       ↙️                  ⬇️                     ↘️
+-------------+    +-------------+         +-------------+
| Grammar Bot |    | Context Bot |         | Expression  |
| (vLLM API)  |    | (vLLM API)  |         | (vLLM API)  |
+-------------+    +-------------+         +-------------+
       ↘️                  ⬇️                     ↙️
        +-----------------------------------------+
        |             Evaluator (Judge)           |
        |   * Uses Fine-tuned Model for Scoring   |
        +-----------------------------------------+
                           ⬇️
                     [ Feedback ]

```

---

## 🛠️ Tech Stack & Skills

### AI Core & Optimization

* **Orchestration:** LangChain, LangGraph (Stateful Multi-Agent System)
* **Model Serving (Inference):** **vLLM** (PagedAttention 적용, Throughput 2배 향상)
* **Fine-tuning:** **LoRA/QLoRA** (Qwen 2.5 기반 한국어 교육 데이터 학습)
* **Prompt Engineering:** Chain-of-Thought (CoT), Few-shot Prompting for Evaluation

### Backend & Data Engineering

* **Server:** Python 3.11, FastAPI (Asynchronous)
* **RAG Pipeline:** Vector DB (PGVector) 
* **Task Queue:** Redis Queue (RQ) for Background Processing
* **Database:** SQLAlchemy (PostgreSQL/MySQL), Redis (Session Store)

---

## 💡 Key Features (Technical Highlights)

### 1. vLLM 기반 초고속 추론 서빙 (High-Performance Serving)

실시간 대화의 몰입감을 위해 응답 속도가 핵심입니다. 기존 방식 대비 **vLLM**을 도입하여 추론 성능을 최적화했습니다.

* **PagedAttention 적용:** KV 캐시 메모리 효율을 극대화하여 동시 접속자 처리를 원활하게 함.
* **Continuous Batching:** 여러 에이전트의 동시다발적 요청을 배치로 묶어 처리함으로써 GPU 활용률(Utilization) 극대화.
* **Latency 개선:** 토큰 생성 속도(TPS)를 ollama 대비 약 1.5~2배 향상시켜 실시간 튜터링 경험 제공.

### 2. 교육 도메인 특화 Fine-tuning (Domain Adaptation)

범용 LLM은 한국어 교육의 미세한 뉘앙스나 '세종학당 평가 기준'을 완벽히 이해하지 못하는 문제가 있었습니다.

* **데이터셋 구축:** 한국어 학습자 오류 데이터셋(Grammatical Error Correction)과 모범 답안 쌍을 구축.
* **PEFT (LoRA):** 전체 파라미터 튜닝 대신 LoRA(Low-Rank Adaptation)를 적용하여 적은 리소스로 레벨별 Adaptor 생성.
* **결과:** 할루시네이션(Hallucination) 감소 및 피드백의 수준별 응답 가능.

### 3. LangGraph 기반 평가 전문가 시스템 (`agent/judge`)

단일 모델에 의존하지 않고, 전문화된 에이전트들이 협업하는 **Mixture of Experts (MoE) 유사 구조**를 구현했습니다.

* **Supervisor:** 사용자의 입력 의도를 파악하고 적절한 워커(Worker)에게 작업을 분배.
* **Analysts:** 문법, 맥락, 표현력을 담당하는 에이전트들이 파인튜닝된 모델을 통해 정밀 분석 수행.
* **State Management:** 대화의 흐름과 평가 상태를 그래프(Graph) 형태로 관리하여 복잡한 로직 제어.

---

## 📂 Project Structure

```bash
k-lingo-ai-server/
├── agent/                  # [Core] AI 에이전트 & LangGraph 로직
│   ├── judge/              # 평가 전문 에이전트 (Multi-Agent System)
│   │   ├── nodes/          # 실행 노드 (Supervisor, Analysts, Tutor, Evaluator)
│   │   ├── prompts/        # 에이전트 페르소나 및 평가 프롬프트 (YAML)
│   │   ├── utils/          # 세종학당 평가 기준 등 로직 유틸
│   │   └── workflow.py     # LangGraph 상태 그래프(StateGraph) 정의
│   └── supervisor.py       # 에이전트 관리 및 분기 처리
│
├── api/                    # [Service] FastAPI 도메인별 라우터
│   ├── chat/               # LLM 채팅 서비스 (vLLM / Ollama 연동)
│   ├── evaluation/         # 학습자 발화 평가 및 피드백 생성 API
│   ├── listening/          # 리스닝(듣기) 학습 관련 API
│   ├── speaking/           # 스피킹(말하기) 및 음성 처리 API
│   ├── write/              # 작문 학습 및 OCR(손글씨 인식) API
│   └── general/            # 공통 비즈니스 로직
│       ├── service/        # 시나리오 진행(RL), 진척도 관리 서비스
│       ├── task/           # 백그라운드 작업 (시나리오 생성 등)
│       └── ...             # 유저, 상점, 아이템, 어드민 관리
│
├── common/                 # [Utils] 공통 유틸리티 라이브러리
│   ├── ko_util.py          # 한국어 전처리 및 텍스트 분석 도구
│   ├── evaluation.py       # 평가 관련 공통 함수
│   └── file_util.py        # 파일 입출력 헬퍼
│
├── db/                     # [Data] 데이터베이스 및 저장소 계층
│   ├── model/              # SQLAlchemy ORM 모델 (User, Scenario, Item 등)
│   ├── vectordb.py         # RAG용 Vector DB 인터페이스 (Embeddings)
│   ├── redis.py            # Redis 연결 (캐싱 및 세션)
│   └── database.py         # DB 세션 매니저
│
├── mcp_tools/              # [Tools] 외부 도구 연동 (Model Context Protocol)
│   └── brave_search.py     # 웹 검색 도구 등 확장 기능
│
├── static/                 # [View] 웹 데모 및 리소스
│   ├── images/             # 시스템 다이어그램 및 에셋
│   ├── web/                # 프론트엔드 스크립트 (JS, CSS)
│   └── *.html              # 테스트 및 데모용 페이지
│
├── app.py                  # [Main] FastAPI 앱 실행 진입점 (Entry Point)
├── appadmin.py             # 관리자용 대시보드 진입점
├── start_rq_worker.sh      # [Worker] Redis Queue 비동기 워커 실행 스크립트
└── requirements.txt        # 프로젝트 의존성 목록

```
