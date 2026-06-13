# The CAD Lad

An agentic CAD modeling tool. Describe a mechanical part in plain English. The agent plans, writes CadQuery Python, executes it, renders a preview, and iterates with you. Produce STL files that can be exported for 3D printing.

## Setup

```bash
cp .env.example .env
# Add your OPENAI_API_KEY

docker compose up --build
```

http://localhost:5173 

API docs: http://localhost:8000/docs

## Run tests

```bash
docker compose exec backend pytest
```

## Roadmap

- More robust job queue: replace BackgroundTasks with Celery + Redis
    - Moves code execution subprocess out of API process
    - Enables retries, priority queues, execution timeouts at worker level
    - Uses existing CadJobs table
    
- Enable database migrations: use Aerich to track and implement changes instead of generate_schemas()
    - Aerich is installed and TORTOISE_ORM is exported already
    - Switch to Alembic if switching to SQLAlchemy 2.0 for more complex queries

- Upgrade from SQLite to Postgres database
    - Enable concurrent writes and multiple connections for many users
    - Swap out databse url and add asyncpg
    - Add S3 bucket config to save png and stl artifacts per user/session

- Implement authentication and permissioning
    - Add User model to database and architecture
    - Implement JWT auth initially to scope session perms and file access

- Streaming responses for conversational turns
    - Make conversation chat messages feel much faster (not applicable for tool calls)
    - Utilize sse-starlette which is installed

- Harden and productionize the executor
    - Non-root user, cgroup CPU/memory limits, no external network access
    - Ephemeral container per job (Fargate, Fly Machines)

- Debug application and retrain agent on historical data
    - Utilize session data and CADJobs data to improve code logic and model


