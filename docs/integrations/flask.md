# Flask Integration

## Basic Setup

```python
from logxide import logging

from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@app.route('/')
def hello():
    logger.info('Hello endpoint accessed')
    return jsonify({'message': 'Hello from Flask with LogXide!'})

if __name__ == '__main__':
    app.run(debug=True)
```

## Request Logging Middleware

```python
from logxide import logging

from flask import Flask, request, g
import time

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(thread)d] - %(message)s'
)

access_logger = logging.getLogger('flask.access')
error_logger = logging.getLogger('flask.error')

@app.before_request
def log_request_info():
    """Log incoming request details."""
    g.start_time = time.time()
    access_logger.info(
        f'{request.method} {request.url} - '
        f'User-Agent: {request.headers.get("User-Agent", "Unknown")}'
    )

@app.after_request
def log_request_completion(response):
    """Log request completion with timing."""
    duration = time.time() - g.start_time
    access_logger.info(
        f'{request.method} {request.url} - '
        f'Status: {response.status_code} - '
        f'Duration: {duration:.3f}s'
    )
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Log unhandled exceptions."""
    error_logger.exception(f'Unhandled exception: {str(e)}')
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    logger = logging.getLogger('api.users')
    logger.info(f'Fetching user {user_id}')

    if user_id == 404:
        logger.warning(f'User {user_id} not found')
        return jsonify({'error': 'User not found'}), 404

    logger.info(f'Successfully retrieved user {user_id}')
    return jsonify({'user_id': user_id, 'name': f'User {user_id}'})
```

## Flask-SQLAlchemy Integration

```python
from logxide import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable SQLAlchemy logging through LogXide
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.setLevel(logging.INFO)

app_logger = logging.getLogger('app')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

@app.route('/users', methods=['POST'])
def create_user():
    app_logger.info('Creating new user')

    user = User(username='testuser')
    db.session.add(user)
    db.session.commit()

    app_logger.info(f'User created with ID: {user.id}')
    return {'user_id': user.id, 'username': user.username}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

## Sentry with Flask

See the [Sentry Integration Guide](sentry.md) for detailed Sentry setup. Quick example:

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-dsn",
    integrations=[FlaskIntegration()]
)

from flask import Flask
from logxide import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.errorhandler(500)
def handle_error(error):
    logger.exception("Internal server error", exc_info=error)
    return "Internal Server Error", 500
```
