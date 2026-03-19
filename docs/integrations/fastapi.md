# FastAPI Integration

## Basic Setup

```python
from logxide import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import time

app = FastAPI(title="LogXide FastAPI Integration")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    username: str

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = time.time()

    logger.info(f'{request.method} {request.url.path} - Client: {request.client.host}')

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        f'{request.method} {request.url.path} - '
        f'Status: {response.status_code} - '
        f'Duration: {duration:.3f}s'
    )

    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions."""
    logger.exception(f'Unhandled exception on {request.method} {request.url.path}: {str(exc)}')
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {"message": "FastAPI with LogXide", "status": "running"}

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get user by ID."""
    logger.info(f'Fetching user {user_id}')

    if user_id == 404:
        logger.warning(f'User {user_id} not found')
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f'Successfully retrieved user {user_id}')
    return {"user_id": user_id, "username": f"user_{user_id}"}

@app.post("/users")
async def create_user(user: UserCreate):
    """Create a new user."""
    logger.info(f'Creating user: {user.username}')

    user_id = hash(user.username) % 10000

    logger.info(f'User created: {user.username} (ID: {user_id})')
    return {"user_id": user_id, "username": user.username}
```

## Background Tasks with Logging

```python
from logxide import logging

from fastapi import FastAPI, BackgroundTasks
import asyncio

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(thread)d] - %(message)s'
)

task_logger = logging.getLogger('background_tasks')

async def process_data(task_id: str, data: dict):
    """Background task with logging."""
    task_logger.info(f'Starting background task {task_id}')

    try:
        await asyncio.sleep(2)

        task_logger.info(f'Processing data for task {task_id}: {len(data)} items')

        for i in range(10):
            task_logger.debug(f'Task {task_id} - Processing item {i}')
            await asyncio.sleep(0.1)

        task_logger.info(f'Task {task_id} completed successfully')

    except Exception as e:
        task_logger.error(f'Task {task_id} failed: {str(e)}')
        raise

@app.post("/process")
async def start_processing(background_tasks: BackgroundTasks):
    """Start background processing."""
    task_id = "task_123"
    data = {"items": list(range(100))}

    background_tasks.add_task(process_data, task_id, data)

    logger.info(f'Queued background task {task_id}')
    return {"task_id": task_id, "status": "queued"}
```

## Database Integration (SQLAlchemy)

```python
from logxide import logging

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.setLevel(logging.INFO)

app_logger = logging.getLogger('fastapi.app')

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/")
async def create_user(username: str, db: Session = Depends(get_db)):
    """Create user with database logging."""
    app_logger.info(f'Creating user: {username}')

    db_user = User(username=username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    app_logger.info(f'User created: {username} (ID: {db_user.id})')
    return {"user_id": db_user.id, "username": db_user.username}

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user with database logging."""
    app_logger.info(f'Fetching user {user_id}')

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        app_logger.warning(f'User {user_id} not found')
        raise HTTPException(status_code=404, detail="User not found")

    app_logger.info(f'Successfully retrieved user {user_id}')
    return {"user_id": user.id, "username": user.username}
```

## Sentry with FastAPI

See the [Sentry Integration Guide](sentry.md) for detailed Sentry setup. Quick example:

```python
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

sentry_sdk.init(dsn="your-dsn")

from fastapi import FastAPI
from logxide import logging

app = FastAPI()
app.add_middleware(SentryAsgiMiddleware)

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def exception_handler(request, exc):
    logger.exception("Unhandled exception", exc_info=exc)
    return {"error": "Internal server error"}
```
