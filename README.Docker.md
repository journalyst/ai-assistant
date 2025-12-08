# Journalyst AI Assistant - Docker Deployment

## Quick Start

### 1. Set up environment variables

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY or OPENAI_API_KEY
```

### 2. Start the full stack

```bash
docker compose up --build
```

This will start:
- **API Server**: http://localhost:8000 (with test client UI)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **Qdrant**: http://localhost:6333

### 3. Access the application

- **Test Client UI**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Services

| Service | Port | Description |
|---------|------|-------------|
| server | 8000 | FastAPI application |
| postgres | 5432 | PostgreSQL database |
| redis | 6379 | Redis cache & sessions |
| qdrant | 6333 | Vector database for journals |

## Common Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f server

# Stop all services
docker compose down

# Reset all data (removes volumes)
docker compose down -v

# Rebuild after code changes
docker compose up --build

# Run only dependencies (for local development)
docker compose up -d postgres redis qdrant
```

## Development vs Production

### Local Development (without Docker for API)
```bash
# Start only infrastructure
docker compose up -d postgres redis qdrant

# Run API locally with uv
uv run uvicorn src.api.app:app --reload --port 8000
```

### Production Deployment
```bash
# Build for production
docker build -t journalyst-ai:latest .

# Run with external services
docker run -d \
  -p 8000:8000 \
  -e POSTGRES_RW_DSN=postgresql://user:pass@your-db:5432/journalyst \
  -e REDIS_URL=redis://your-redis:6379/0 \
  -e QDRANT_URL=http://your-qdrant:6333 \
  -e OPENROUTER_API_KEY=your_key \
  journalyst-ai:latest
```

## Multi-Platform Build

For cloud deployment on different architectures:

```bash
# Build for AMD64 (most cloud providers)
docker build --platform=linux/amd64 -t journalyst-ai:latest .

# Build for ARM64 (AWS Graviton, Apple Silicon)
docker build --platform=linux/arm64 -t journalyst-ai:latest .
```

## Seeding Data

The PostgreSQL container automatically seeds data from `sample_data/seed_data.sql` on first run.

To seed journal entries into Qdrant:
```bash
docker compose exec server uv run python -m src.data_seeding.seed_journals
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker compose logs server

# Verify dependencies are healthy
docker compose ps
```

### Database connection issues
```bash
# Verify PostgreSQL is ready
docker compose exec postgres pg_isready -U journalyst

# Check Redis
docker compose exec redis redis-cli ping
```

### Reset everything
```bash
docker compose down -v
docker compose up --build
```