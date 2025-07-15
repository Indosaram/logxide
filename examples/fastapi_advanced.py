#!/usr/bin/env python3
"""
Advanced FastAPI Integration Example with LogXide

This example demonstrates comprehensive FastAPI integration with LogXide,
showcasing async logging, database operations, background tasks, WebSocket
logging, dependency injection, and comprehensive error handling.
"""

import logxide

logxide.install()

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fastapi_logxide_demo.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Configure LogXide with comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(thread)d] - %(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create specialized loggers
app_logger = logging.getLogger("fastapi.app")
request_logger = logging.getLogger("fastapi.requests")
db_logger = logging.getLogger("fastapi.database")
task_logger = logging.getLogger("fastapi.background_tasks")
websocket_logger = logging.getLogger("fastapi.websockets")
performance_logger = logging.getLogger("fastapi.performance")

# Enable SQLAlchemy logging through LogXide
sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
sqlalchemy_logger.setLevel(logging.INFO)


# Database Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    method = Column(String)
    path = Column(String)
    status_code = Column(Integer)
    duration = Column(Float)
    user_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Pydantic Models
class UserCreate(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class PerformanceMetrics(BaseModel):
    total_requests: int
    average_response_time: float
    status_code_distribution: dict[str, int]
    recent_requests: list[dict[str, Any]]


# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        websocket_logger.info(
            f"WebSocket connection established. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        websocket_logger.info(
            f"WebSocket connection closed. Total connections: {len(self.active_connections)}"
        )

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        websocket_logger.info(
            f"Broadcasting message to {len(self.active_connections)} connections"
        )
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                websocket_logger.error(
                    f"Failed to send message to connection: {str(e)}"
                )


manager = ConnectionManager()


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Utility functions
def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, user: UserCreate):
    db_user = User(username=user.username, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_task(db: Session, task: TaskCreate):
    task_id = str(uuid.uuid4())
    db_task = Task(id=task_id, title=task.title, description=task.description)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


# Background Tasks
async def process_long_running_task(task_id: str, data: dict[str, Any]):
    """Simulate a long-running background task with logging."""
    task_logger.info(f"Starting background task {task_id}")

    try:
        # Simulate processing steps
        steps = ["initializing", "processing", "validating", "finalizing"]

        for i, step in enumerate(steps):
            task_logger.info(f"Task {task_id} - Step {i + 1}/4: {step}")

            # Simulate work
            await asyncio.sleep(2)

            # Broadcast progress via WebSocket
            await manager.broadcast(
                json.dumps(
                    {
                        "task_id": task_id,
                        "status": step,
                        "progress": (i + 1) / len(steps) * 100,
                    }
                )
            )

        # Update task status in database
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "completed"
                task.completed_at = datetime.utcnow()
                db.commit()
                task_logger.info(f"Task {task_id} completed successfully")
        finally:
            db.close()

        # Final broadcast
        await manager.broadcast(
            json.dumps({"task_id": task_id, "status": "completed", "progress": 100})
        )

    except Exception as e:
        task_logger.error(f"Task {task_id} failed: {str(e)}")

        # Update task status to failed
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                db.commit()
        finally:
            db.close()

        await manager.broadcast(
            json.dumps({"task_id": task_id, "status": "failed", "error": str(e)})
        )


async def log_performance_metrics():
    """Background task to log performance metrics."""
    while True:
        try:
            db = SessionLocal()

            # Calculate metrics
            total_requests = db.query(RequestLog).count()

            if total_requests > 0:
                from sqlalchemy import func

                avg_duration = db.query(func.avg(RequestLog.duration)).scalar()

                performance_logger.info(
                    f"Performance metrics - Total requests: {total_requests}, "
                    f"Average response time: {avg_duration:.3f}s"
                )

            db.close()

        except Exception as e:
            performance_logger.error(f"Error calculating performance metrics: {str(e)}")

        # Wait 60 seconds before next calculation
        await asyncio.sleep(60)


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app_logger.info("Starting FastAPI application with LogXide")

    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Start background performance monitoring
    performance_task = asyncio.create_task(log_performance_metrics())

    try:
        yield
    finally:
        # Shutdown
        app_logger.info("Shutting down FastAPI application")

        # Cancel background tasks
        performance_task.cancel()

        # Ensure all logs are flushed
        logging.flush()


# Create FastAPI app
app = FastAPI(
    title="LogXide FastAPI Advanced Integration",
    description="Comprehensive FastAPI integration with LogXide featuring async logging, WebSockets, and background tasks",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all HTTP requests with comprehensive details."""
    start_time = time.time()

    # Log request start
    request_logger.info(
        f"{request.method} {request.url.path} - "
        f"Client: {request.client.host} - "
        f"User-Agent: {request.headers.get('user-agent', 'Unknown')}"
    )

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log response
    request_logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration:.3f}s"
    )

    # Store request log in database (async)
    try:
        db = SessionLocal()
        request_log = RequestLog(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=duration,
        )
        db.add(request_log)
        db.commit()
        db.close()
    except Exception as e:
        db_logger.error(f"Failed to log request to database: {str(e)}")

    return response


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    app_logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle all other exceptions."""
    app_logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# API Routes
@app.get("/")
async def root():
    """Root endpoint with API information."""
    app_logger.info("Root endpoint accessed")
    return {
        "message": "FastAPI Advanced Integration with LogXide",
        "features": [
            "Async logging with Rust performance",
            "Database integration with SQLAlchemy",
            "Background tasks with logging",
            "WebSocket support with real-time logging",
            "Comprehensive error handling",
            "Performance monitoring",
        ],
        "endpoints": {
            "users": "/users",
            "tasks": "/tasks",
            "websocket": "/ws",
            "health": "/health",
            "metrics": "/metrics",
            "performance": "/performance-test",
        },
    }


@app.get("/users", response_model=list[UserResponse])
async def get_users(db: Session = Depends(get_db)):  # noqa: B008
    """Get all users."""
    app_logger.info("Fetching all users")

    users = db.query(User).all()
    app_logger.info(f"Found {len(users)} users")

    return users


@app.post("/users", response_model=UserResponse)
async def create_user_endpoint(user: UserCreate, db: Session = Depends(get_db)):  # noqa: B008
    """Create a new user."""
    app_logger.info(f"Creating user: {user.username}")

    # Check if user already exists
    existing_user = get_user_by_username(db, user.username)
    if existing_user:
        app_logger.warning(f"User {user.username} already exists")
        raise HTTPException(status_code=400, detail="Username already exists")

    try:
        db_user = create_user(db, user)
        app_logger.info(
            f"User created successfully: {user.username} (ID: {db_user.id})"
        )
        return db_user
    except Exception as e:
        app_logger.error(f"Failed to create user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create user") from e


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):  # noqa: B008
    """Get user by ID."""
    app_logger.info(f"Fetching user {user_id}")

    user = get_user_by_id(db, user_id)
    if not user:
        app_logger.warning(f"User {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")

    app_logger.info(f"Successfully retrieved user {user_id}")
    return user


@app.get("/tasks", response_model=list[TaskResponse])
async def get_tasks(db: Session = Depends(get_db)):  # noqa: B008
    """Get all tasks."""
    app_logger.info("Fetching all tasks")

    tasks = db.query(Task).all()
    app_logger.info(f"Found {len(tasks)} tasks")

    return tasks


@app.post("/tasks", response_model=TaskResponse)
async def create_task_endpoint(
    task: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
):
    """Create a new task and start background processing."""
    app_logger.info(f"Creating task: {task.title}")

    try:
        db_task = create_task(db, task)

        # Start background processing
        background_tasks.add_task(
            process_long_running_task,
            db_task.id,
            {"title": task.title, "description": task.description},
        )

        app_logger.info(f"Task created and background processing started: {db_task.id}")
        return db_task

    except Exception as e:
        app_logger.error(f"Failed to create task: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create task") from e


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)):  # noqa: B008
    """Get task by ID."""
    app_logger.info(f"Fetching task {task_id}")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        app_logger.warning(f"Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")

    app_logger.info(f"Successfully retrieved task {task_id}")
    return task


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            websocket_logger.info(f"Received WebSocket message: {data}")

            # Echo message back
            await manager.send_personal_message(f"Echo: {data}", websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        websocket_logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):  # noqa: B008
    """Health check endpoint."""
    app_logger.info("Health check requested")

    # Check database connection
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "logging": "logxide",
        "websocket_connections": len(manager.active_connections),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/metrics", response_model=PerformanceMetrics)
async def get_metrics(db: Session = Depends(get_db)):  # noqa: B008
    """Get comprehensive API metrics."""
    app_logger.info("Metrics requested")

    try:
        # Get request statistics
        total_requests = db.query(RequestLog).count()

        # Calculate average response time
        from sqlalchemy import func

        avg_duration = db.query(func.avg(RequestLog.duration)).scalar() or 0

        # Get status code distribution
        status_counts = (
            db.query(RequestLog.status_code, func.count(RequestLog.id))
            .group_by(RequestLog.status_code)
            .all()
        )

        # Get recent requests
        recent_requests = (
            db.query(RequestLog).order_by(RequestLog.timestamp.desc()).limit(10).all()
        )

        metrics = PerformanceMetrics(
            total_requests=total_requests,
            average_response_time=round(avg_duration, 3),
            status_code_distribution={
                str(status): count for status, count in status_counts
            },
            recent_requests=[
                {
                    "method": req.method,
                    "path": req.path,
                    "status_code": req.status_code,
                    "duration": req.duration,
                    "timestamp": req.timestamp.isoformat(),
                }
                for req in recent_requests
            ],
        )

        app_logger.info(f"Metrics retrieved: {total_requests} total requests")
        return metrics

    except Exception as e:
        app_logger.error(f"Failed to retrieve metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics") from e


@app.get("/performance-test")
async def performance_test(count: int = 1000):
    """Test logging performance with high volume."""
    app_logger.info(f"Starting performance test with {count} log messages")

    start_time = time.time()

    # Generate many log messages
    for i in range(count):
        performance_logger.debug(f"Performance test message {i + 1}/{count}")

    # Time to queue all messages
    queue_time = time.time() - start_time

    # Flush logs and measure total time
    logging.flush()
    total_time = time.time() - start_time

    app_logger.info(
        f"Performance test completed: {count} messages in {total_time:.3f}s "
        f"({count / total_time:.0f} msg/sec)"
    )

    return {
        "messages": count,
        "queue_time": f"{queue_time:.3f}s",
        "total_time": f"{total_time:.3f}s",
        "messages_per_second": round(count / total_time, 2),
        "logging_backend": "logxide",
    }


@app.get("/stress-test")
async def stress_test(duration: int = 30):
    """Stress test with continuous logging."""
    app_logger.info(f"Starting stress test for {duration} seconds")

    start_time = time.time()
    message_count = 0

    while time.time() - start_time < duration:
        performance_logger.info(f"Stress test message {message_count + 1}")
        message_count += 1

        # Small delay to avoid overwhelming the system
        await asyncio.sleep(0.001)

    total_time = time.time() - start_time

    # Flush all logs
    logging.flush()

    app_logger.info(
        f"Stress test completed: {message_count} messages in {total_time:.3f}s "
        f"({message_count / total_time:.0f} msg/sec)"
    )

    return {
        "duration": f"{total_time:.3f}s",
        "messages": message_count,
        "messages_per_second": round(message_count / total_time, 2),
        "logging_backend": "logxide",
    }


if __name__ == "__main__":
    import uvicorn

    app_logger.info("Starting FastAPI server with LogXide integration")

    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=False,  # We handle our own access logging
        )
    except KeyboardInterrupt:
        app_logger.info("Server interrupted by user")
    except Exception as e:
        app_logger.error(f"Server error: {str(e)}")
    finally:
        logging.flush()
        app_logger.info("Server shutdown complete")
