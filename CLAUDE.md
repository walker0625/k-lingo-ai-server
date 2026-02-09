# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**K-Lingo AI Server** is a high-performance, multi-agent Korean language education AI tutoring system. It combines:
- **Fine-tuned LLMs** (LoRA-adapted for Korean education)
- **Multi-Agent Orchestration** (LangGraph-based evaluation system)
- **High-speed Inference** (vLLM with PagedAttention)
- **Multimodal AI** (Speech: STT/TTS, Vision: OCR, Text: LLM)

Core focus: Diagnostics and correction of learner speech based on educational standards (Sejong Academy criteria).

## Quick Start Commands

### Setup & Installation
```bash
# Create virtual environment (Python 3.11 required)
python3.11 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file with required variables
cp .env.example .env  # If available, or create manually
```

### Running the Application

**Main FastAPI Server** (port 8104):
```bash
python app.py
# Or with auto-reload for development:
uvicorn app:app --reload --port 8104
```

**Admin Dashboard** (SQLAdmin):
```bash
python appadmin.py
```

**Redis Queue Worker** (for async background tasks):
```bash
bash start_rq_worker.sh
# Or manually:
rq worker --url redis://localhost:6379 KLINGO:RQ
```

### Environment Variables (Required)

Create a `.env` file with these variables:
```
DATABASE_URL=postgresql://user:password@localhost:5432/klingo
DATABASE_INIT=1  # Set to 0 to reset/drop all tables on startup
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-xxx  # For GPT-4 fallback evaluations
VLLM_API_URL=http://localhost:8000  # vLLM inference server (optional)
```

### Initialize Database

```bash
# Populate initial test data (users, scenarios, interviews)
python insert_init_data.py
```

## Architecture & Design Patterns

### High-Level System Flow

```
[HTTP Request]
    ↓
[FastAPI Router] (api/*)
    ↓
[Service Layer] (*_service.py)
    ↓
[LangGraph Agent] (agent/judge/workflow.py) or [Business Logic]
    ↓
[Data Layer] (db/model/*, db/database.py)
    ↓
[PostgreSQL + Redis]
```

### Multi-Agent Evaluation Workflow (Core Innovation)

The `agent/judge/workflow.py` implements a **LangGraph StateGraph** with 5 nodes:

1. **Supervisor** (`nodes/supervisor.py`): Entry point
   - Determines which worker to dispatch based on `AssessmentState`
   - Handles **error detection, retry logic (max 3 attempts), and fallback responses**
   - Tracks `error_states` and `retry_counts` for each node

2. **Analysts** (parallel execution):
   - **Linguist** (`nodes/analysts.py`): Grammar analysis
   - **Context Analyst** (`nodes/analysts.py`): Contextual appropriateness
   - Each calls fine-tuned LLM via vLLM API

3. **Evaluator** (`nodes/evaluator.py`): Scoring & weighting
   - Combines grammar + context scores
   - Returns final score and pass/fail decision

4. **Tutor** (`nodes/tutor.py`): Personalized feedback
   - Generates level-appropriate corrections
   - Uses feedback_tutor for user-friendly responses

**Key Pattern**: All nodes return updates to shared `AssessmentState` (TypedDict), flowing back to Supervisor for conditional routing.

### Critical Files for Multi-Agent Flow

- `agent/judge/states.py`: State definition (fields: user_text, grammar_result, error_states, retry_counts, etc.)
- `agent/judge/supervisor.py`: Retry logic & error handling (MAX_RETRY_COUNT = 3)
- `agent/judge/workflow.py`: Graph definition & conditional edges
- `agent/judge/nodes/*.py`: Individual worker implementations

### API Routing Pattern

All domain APIs follow this structure:
```
api/{domain}/
├── {domain}_router.py      # FastAPI route definitions (@app.get, @app.post)
├── {domain}_service.py     # Business logic layer
├── dto/
│   └── {domain}_dto.py     # Pydantic request/response schemas
└── __init__.py
```

Example: `api/evaluation/evaluation_router.py` → `api/evaluation/evaluation_service.py` → `EvaluationService.evaluate_room()`

### Database Layer

- **ORM**: SQLModel (combines SQLAlchemy + Pydantic)
- **Models**: `db/model/*.py` (User, Scenario, Progress, Character, etc.)
- **Session Management**: `db/database.py` (DBHandler class)
- **Vector DB**: PGVector extension for RAG embeddings
- **Caching**: Redis (via `db/redis.py`)

Tables automatically created on startup if `DATABASE_INIT=0`.

## Code Organization

### `/api` - HTTP Endpoints
- `chat/`: LLM conversation API (vLLM/Ollama backed)
- `evaluation/`: Core multi-agent evaluation endpoint
- `listening/`: Listening comprehension exercises
- `speaking/`: Speech processing (STT/TTS)
- `write/`: Writing exercises with OCR support
- `general/`: User management, scenarios, characters, store

### `/agent` - AI Logic
- `judge/workflow.py`: LangGraph state machine
- `judge/nodes/`: Worker node implementations
- `judge/supervisor.py`: Orchestration & error handling
- `judge/prompts/`: YAML-based agent personas and evaluation criteria

### `/db` - Data Access
- `model/`: SQLModel table definitions
- `database.py`: Engine & session management
- `redis.py`: Redis client wrapper
- `vectordb.py`: PGVector interface for embeddings

### `/common` - Utilities
- `ko_util.py`: Korean text processing (hangul decomposition, romanization)
- `evaluation.py`: Shared scoring functions
- `file_util.py`: File I/O helpers
- `path.py`: Path configurations

## Logging & Monitoring

- **Logger**: Loguru (configured in `loguru_config.py`)
- **File logs**: `logs/api_{YYYY-MM-DD}.log` (rotated daily, 7-day retention)
- **Console logs**: Colored output with function/line info
- **Request tracking**: All HTTP requests logged with body (except multipart)

Access logs:
```bash
tail -f logs/api_*.log
```

## Common Development Tasks

### Adding a New API Endpoint

1. Create/edit `api/{domain}/{domain}_router.py`:
   ```python
   from fastapi import APIRouter, HTTPException
   from api.{domain}.{domain}_service import {Domain}Service

   router = APIRouter()

   @router.get("/path/{id}")
   def my_endpoint(id: int, session: SessionDep):
       service = {Domain}Service()
       return service.do_something(id, session)
   ```

2. Create `api/{domain}/{domain}_service.py` with business logic
3. Define DTOs in `api/{domain}/dto/{domain}_dto.py`
4. Register router in `app.py`: `app.include_router(router, prefix="/{domain}", tags=["{domain}"])`

### Modifying the Evaluation Workflow

1. Edit `agent/judge/nodes/{node_name}.py` to change worker logic
2. Update `agent/judge/prompts/` YAML files if changing evaluation criteria
3. Modify `agent/judge/states.py` if adding/removing state fields
4. Update `agent/judge/supervisor.py` if changing routing logic
5. Test by calling evaluation endpoint: `POST /evaluations/rooms/{room_id}`

### Adding a New Database Model

1. Create model in `db/model/{model_name}.py`:
   ```python
   from sqlmodel import SQLModel, Field

   class MyModel(SQLModel, table=True):
       id: Optional[int] = Field(default=None, primary_key=True)
       name: str
   ```

2. Import in `db/model/__init__.py` (if needed for batch initialization)
3. Set `DATABASE_INIT=0` on next startup to auto-create table
4. Update relevant service classes to use the model

### Running Async Background Tasks

Tasks are queued in Redis and processed by RQ workers:

```python
from api.general.task.speak_scenario_task import generate_speak_scenario
from rq import Queue
from db.redis import redis_conn

q = Queue(connection=redis_conn)
job = q.enqueue(generate_speak_scenario, args=(scenario_id,))
```

Worker processes jobs from `KLINGO:RQ` queue (see `start_rq_worker.sh`).

## Testing & Debugging

### Debug FastAPI App Locally

Use VS Code debugger (`.vscode/launch.json`):
```json
{
  "name": "Python Debugger: FastAPI",
  "type": "debugpy",
  "request": "launch",
  "module": "uvicorn",
  "args": ["app:app", "--reload"]
}
```

Press F5 to start debugging.

### Test API Endpoints

```bash
# Using curl
curl -X POST http://localhost:8104/evaluations/rooms/1

# Using Python requests
python -c "import requests; print(requests.post('http://localhost:8104/evaluations/rooms/1').json())"
```

### Check Agent Workflow

LangGraph execution can be traced via logs:
```bash
grep "supervisor\|linguist\|context_analyst\|evaluator" logs/api_*.log
```

## Performance Considerations

1. **vLLM Backend**: Inference server uses PagedAttention & continuous batching. Ensure it's running separately for production.
2. **Parallel Agent Execution**: The 3 analyst nodes execute in parallel, then results merge at evaluator.
3. **Redis Caching**: Session state stored in Redis to reduce DB queries.
4. **Database Indexes**: Key columns (username, title, room_id) are indexed.
5. **Async I/O**: FastAPI routes are async; ensure service methods handle DB sessions properly.

## Known Limitations & TODOs

- Milvus vector DB replaced with PGVector; see commented lines in `app.py`
- vLLM inference server URL hardcoded in some services (should be env var)
- OCR (PaddleOCR) requires significant GPU memory; consider CPU mode for dev

## Third-Party Integrations

- **OpenAI API**: For GPT-4 fallback evaluations (requires `OPENAI_API_KEY`)
- **ElevenLabs**: TTS service (optional, for speech synthesis)
- **PaddleOCR**: Handwriting/image text recognition
- **PostgreSQL + pgvector**: Main DB with vector embedding support
- **Redis**: Session/cache backend

## Key Metrics & Success Indicators

- **Evaluation latency**: Target &lt; 2s for complete assessment
- **vLLM throughput**: ~2x faster than Ollama (via PagedAttention)
- **Multi-agent parallelization**: 3 analysts run simultaneously
- **Error recovery**: Automatic retry up to 3 times with fallback
