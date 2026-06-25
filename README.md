# AI Interview Agent

An autonomous AI-powered technical interviewer built with FastAPI and Claude API.

## Quick Start

### Prerequisites
- Python 3.12+
- [Optional] Docker (for PostgreSQL + Redis)

### Setup

```bash
# 1. Clone and enter the project
cd agent-interview

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
cd backend
pip install -r requirements.txt

# 4. Configure environment
cp ../.env.example ../.env
# Edit .env and add your ANTHROPIC_API_KEY

# 5. (Optional) Start PostgreSQL + Redis via Docker
docker compose up -d

# 6. Run the server
python -m uvicorn app.main:app --reload --port 8000
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/sessions` | Create interview session |
| GET | `/api/sessions/{id}` | Get session status |
| GET | `/api/sessions/{id}/report` | Get interview report |
| DELETE | `/api/sessions/{id}` | Delete session |
| WS | `/ws/interview/{id}` | Conduct interview |

### Usage

1. Create a session via REST API
2. Connect via WebSocket using the returned session ID
3. The AI interviewer will guide the conversation

### Running Tests

```bash
cd backend
pytest tests/ -v
```

### Architecture

```
Client (WebSocket/REST)
    │
    ▼
FastAPI
    │
    ├── InterviewAgent (orchestrator)
    │   ├── InterviewFSM (state machine)
    │   ├── ConversationManager (sliding window + intent)
    │   ├── EvaluationEngine (LLM scoring)
    │   └── QuestionBankService (adaptive difficulty)
    │
    ├── ClaudeAdapter (Anthropic API)
    │
    └── PostgreSQL / SQLite (persistence)
```
