#!/usr/bin/env python3
"""
Flask Integration Example with LogXide

This example demonstrates comprehensive Flask integration with LogXide,
showcasing request logging, error handling, database operations, and
performance monitoring.
"""

import logxide

logxide.install()

import logging
import os
import time
from functools import wraps

from flask import Flask, g, jsonify, request
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///flask_demo.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db = SQLAlchemy(app)

# Configure LogXide with structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(thread)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create specialized loggers
app_logger = logging.getLogger("flask.app")
access_logger = logging.getLogger("flask.access")
error_logger = logging.getLogger("flask.error")
db_logger = logging.getLogger("flask.database")

# Enable SQLAlchemy logging through LogXide
sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
sqlalchemy_logger.setLevel(logging.INFO)


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


class ApiLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    method = db.Column(db.String(10), nullable=False)
    path = db.Column(db.String(200), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


# Decorators
def log_performance(func):
    """Decorator to log function performance."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            app_logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            error_logger.error(
                f"{func.__name__} failed after {duration:.3f}s: {str(e)}"
            )
            raise

    return wrapper


def get_client_ip():
    """Get client IP address."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0]
    return request.remote_addr


# Request Logging Middleware
@app.before_request
def log_request_info():
    """Log incoming request details."""
    g.start_time = time.time()
    g.client_ip = get_client_ip()

    access_logger.info(
        f"{request.method} {request.path} - "
        f"Client: {g.client_ip} - "
        f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
    )


@app.after_request
def log_request_completion(response):
    """Log request completion and store metrics."""
    duration = time.time() - g.start_time

    # Log completion
    access_logger.info(
        f"{request.method} {request.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration:.3f}s"
    )

    # Store API metrics (async operation won't block response)
    try:
        api_log = ApiLog(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration=duration,
        )
        db.session.add(api_log)
        db.session.commit()
        db_logger.debug(f"API metrics logged for {request.method} {request.path}")
    except Exception as e:
        db_logger.error(f"Failed to log API metrics: {str(e)}")

    return response


# Error Handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    error_logger.warning(f"404 Not Found: {request.method} {request.path}")
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    error_logger.error(
        f"500 Internal Server Error: {request.method} {request.path}", exc_info=True
    )
    db.session.rollback()
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all other exceptions."""
    error_logger.exception(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500


# API Routes
@app.route("/")
def index():
    """Root endpoint."""
    app_logger.info("Index page accessed")
    return jsonify(
        {
            "message": "Flask + LogXide Integration Demo",
            "endpoints": [
                "/",
                "/users",
                "/users/<id>",
                "/health",
                "/metrics",
                "/performance-test",
                "/error-test",
            ],
        }
    )


@app.route("/users", methods=["GET", "POST"])
@log_performance
def users():
    """Handle user operations."""
    if request.method == "GET":
        app_logger.info("Fetching all users")

        users = User.query.all()
        app_logger.info(f"Found {len(users)} users")

        return jsonify(
            {"users": [user.to_dict() for user in users], "count": len(users)}
        )

    elif request.method == "POST":
        app_logger.info("Creating new user")

        data = request.get_json()
        if not data or "username" not in data or "email" not in data:
            app_logger.warning("Invalid user data provided")
            return jsonify({"error": "Username and email are required"}), 400

        try:
            user = User(username=data["username"], email=data["email"])
            db.session.add(user)
            db.session.commit()

            app_logger.info(f"User created: {user.username} (ID: {user.id})")
            return jsonify(user.to_dict()), 201

        except Exception as e:
            db.session.rollback()
            error_logger.error(f"Failed to create user: {str(e)}")
            return jsonify({"error": "Failed to create user"}), 500


@app.route("/users/<int:user_id>")
@log_performance
def get_user(user_id):
    """Get user by ID."""
    app_logger.info(f"Fetching user {user_id}")

    user = User.query.get(user_id)
    if not user:
        app_logger.warning(f"User {user_id} not found")
        return jsonify({"error": "User not found"}), 404

    app_logger.info(f"Successfully retrieved user {user_id}")
    return jsonify(user.to_dict())


@app.route("/health")
def health_check():
    """Health check endpoint."""
    app_logger.info("Health check requested")

    # Check database connection
    try:
        db.session.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"

    return jsonify(
        {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "database": db_status,
            "logging": "logxide",
        }
    )


@app.route("/metrics")
def get_metrics():
    """Get API usage metrics."""
    app_logger.info("Metrics requested")

    try:
        # Recent API calls
        recent_calls = ApiLog.query.order_by(ApiLog.timestamp.desc()).limit(100).all()

        # Calculate average response time
        avg_duration = db.session.query(db.func.avg(ApiLog.duration)).scalar() or 0

        # Count by status code
        status_counts = (
            db.session.query(ApiLog.status_code, db.func.count(ApiLog.id))
            .group_by(ApiLog.status_code)
            .all()
        )

        metrics = {
            "total_requests": ApiLog.query.count(),
            "average_response_time": round(avg_duration, 3),
            "status_code_distribution": {
                str(status): count for status, count in status_counts
            },
            "recent_calls": [
                {
                    "method": call.method,
                    "path": call.path,
                    "status": call.status_code,
                    "duration": call.duration,
                    "timestamp": call.timestamp.isoformat(),
                }
                for call in recent_calls[:10]  # Show only last 10
            ],
        }

        app_logger.info(
            f"Metrics retrieved: {metrics['total_requests']} total requests"
        )
        return jsonify(metrics)

    except Exception as e:
        error_logger.error(f"Failed to retrieve metrics: {str(e)}")
        return jsonify({"error": "Failed to retrieve metrics"}), 500


@app.route("/performance-test")
def performance_test():
    """Test logging performance."""
    count = request.args.get("count", 1000, type=int)
    app_logger.info(f"Starting performance test with {count} log messages")

    start_time = time.time()

    # Generate many log messages
    for i in range(count):
        app_logger.debug(f"Performance test message {i + 1}/{count}")

    # Time to queue all messages
    queue_time = time.time() - start_time

    # Flush logs and measure total time
    logging.flush()
    total_time = time.time() - start_time

    app_logger.info(
        f"Performance test completed: {count} messages in {total_time:.3f}s "
        f"({count / total_time:.0f} msg/sec)"
    )

    return jsonify(
        {
            "messages": count,
            "queue_time": f"{queue_time:.3f}s",
            "total_time": f"{total_time:.3f}s",
            "messages_per_second": round(count / total_time, 2),
        }
    )


@app.route("/error-test")
def error_test():
    """Test error handling and logging."""
    error_type = request.args.get("type", "general")

    app_logger.warning(f"Error test requested: {error_type}")

    if error_type == "division":
        result = 10 / 0  # ZeroDivisionError
    elif error_type == "key":
        data = {}
        value = data["nonexistent_key"]  # KeyError
    elif error_type == "database":
        # Force a database error
        db.session.execute("SELECT * FROM nonexistent_table")
    else:
        raise ValueError(f"Test error: {error_type}")


# Database initialization
def init_db():
    """Initialize database with sample data."""
    with app.app_context():
        db.create_all()

        # Create sample users if none exist
        if User.query.count() == 0:
            sample_users = [
                User(username="alice", email="alice@example.com"),
                User(username="bob", email="bob@example.com"),
                User(username="charlie", email="charlie@example.com"),
            ]

            for user in sample_users:
                db.session.add(user)

            db.session.commit()
            app_logger.info(f"Created {len(sample_users)} sample users")


# CLI Commands
@app.cli.command()
def init_database():
    """Initialize the database."""
    init_db()
    print("Database initialized successfully!")


@app.cli.command()
def test_logging():
    """Test LogXide logging performance."""
    print("Testing LogXide logging performance...")

    start_time = time.time()

    for i in range(10000):
        app_logger.info(f"Test message {i}")

    queue_time = time.time() - start_time

    logging.flush()
    total_time = time.time() - start_time

    print(f"Queued 10,000 messages in {queue_time:.3f}s")
    print(f"Total processing time: {total_time:.3f}s")
    print(f"Messages per second: {10000 / total_time:.0f}")


if __name__ == "__main__":
    # Initialize database
    init_db()

    app_logger.info("Starting Flask application with LogXide")
    app_logger.info(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")

    # Run the application
    try:
        app.run(host="0.0.0.0", port=5001, debug=True)
    finally:
        # Ensure all logs are flushed on shutdown
        logging.flush()
        app_logger.info("Application shutting down")
