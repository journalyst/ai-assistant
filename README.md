# Journalyst AI Assistant

AI-powered trading assistant that analyzes trades and journal entries using natural language queries.

## Quick Start (Docker - Recommended)

The easiest way to run the app is with Docker. This sets up everything automatically.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- An API key from [OpenRouter](https://openrouter.ai/) (free tier available)

### Steps

1. **Clone the repository** (if you haven't already)

2. **Create your environment file**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** and add your API keys:
   ```env
   POSTGRES_USER=journalyst
   POSTGRES_PASSWORD=your_secure_password
   OPENROUTER_API_KEY=your-key-here
   ```

4. **Start the services**
   ```bash
   docker compose up -d
   ```

5. **Seed the database with sample data**
   ```bash
   docker compose exec server ./scripts/seed-data.sh
   ```

6. **Open the app** at [http://localhost:8000](http://localhost:8000)

### Useful Docker Commands

```bash
# View logs in real-time
docker compose logs -f

# View logs for a specific service
docker compose logs -f server

# Stop all services
docker compose down

# Rebuild after code changes
docker compose build server && docker compose up -d

# Seed only PostgreSQL
docker compose exec server ./scripts/seed-data.sh --postgres-only

# Seed only Qdrant (journals)
docker compose exec server ./scripts/seed-data.sh --qdrant-only
```

---

## Local Development Setup (Without Docker)

Use this if you need to make code changes and want hot-reload.

### Prerequisites

- Python 3.10+
- PostgreSQL 15+ running locally
- Redis running locally using Docker
- Qdrant running locally using Docker

### Steps

1. **Create and activate a virtual environment**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies**
   ```powershell
   pip install uv
   uv pip install -r requirements.txt
   ```
   
   Or use the setup script:
   ```powershell
   .\scripts\setup.ps1
   ```

3. **Create your environment file**
   ```powershell
   cp .env.example .env
   ```

4. **Edit `.env`** with your local database credentials and API keys

5. **Start supporting services** (if not using Docker for them)
   
   You can run just the databases in Docker:
   ```bash
   docker compose up -d postgres redis qdrant
   ```

6. **Seed the database**
   ```powershell
   .\scripts\seed-data.ps1
   ```

7. **Run the API server**
   ```powershell
   .\scripts\run-api.ps1
   ```
   
   Or manually:
   ```powershell
   python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
   ```

8. **Open the app** at [http://localhost:8000](http://localhost:8000)

---

## Project Structure

```
AI Assistant/
├── src/
│   ├── api/            # FastAPI endpoints
│   ├── cache/          # Redis session management
│   ├── database/       # PostgreSQL queries & connection
│   ├── data_seeding/   # Sample data scripts
│   ├── llm/            # LLM response generation
│   ├── orchestration/  # Query routing & data retrieval
│   └── vector_db/      # Qdrant journal storage
├── test_client/        # Web UI for testing
├── sample_data/        # Sample SQL & journal data
├── scripts/            # PowerShell scripts (local dev)
├── docker_scripts/     # Bash scripts (Docker)
```

---

## Configuration

All configuration is done via environment variables. See `.env.example` for all options.

### Key Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | Required |
| `ROUTER_MODEL` | Model for query classification | `meta-llama/llama-3.3-70b-instruct:free` |
| `ANALYSIS_MODEL` | Model for response generation | `meta-llama/llama-3.3-70b-instruct:free` |
| `EMBEDDING_PROVIDER` | `local` or `openai` | `local` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |

### Using Different LLM Providers

The app uses [OpenRouter](https://openrouter.ai/) by default, which gives you access to many models. Some free options:

- `openai/gpt-4o-mini` - Fast and capable
- `google/gemma-3-27b-it:free` - Free tier
- `meta-llama/llama-3.3-70b-instruct:free` - Free tier

---