# Python Publisher Subscriber

<!-- markdownlint-disable MD033 -->
<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Flask](https://img.shields.io/badge/Flask-3.0.0-red)
![WebSocket](https://img.shields.io/badge/WebSocket-Enabled-brightgreen)
![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)
![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)
![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)

A high-performance, real-time Publisher-Subscriber system built with Flask, Flask-SocketIO, and SQLite.

[Features](#-features) • [Installation](#-installation) •
[Quick Start](#-quick-start) • [Contributing](#-contributing)

</div>

---

## 🚀 Features

- **Real-time Communication**: WebSocket-based pub/sub messaging with instant delivery
- **Multiple Topics**: Support for subscribing to multiple topics simultaneously
- **Persistent Storage**: SQLite database for message history and consumption tracking
- **Web Interface**: Interactive web client for testing and monitoring
- **Python Client Library**: Easy-to-use Python client for integration
- **RESTful API**: HTTP endpoints for publishing messages
- **Live Monitoring**: Real-time monitoring of connected clients and message consumption
- **Docker Support**: Ready-to-deploy Docker configuration
- **Comprehensive Testing**: Extensive test suite with pytest

- **Type Safety**: Full type hints and mypy validation
- **Production Ready**: Health checks, logging, and error handling

## 📋 Requirements

- Python 3.8 or higher
- pip package manager
- SQLite3

## 🔧 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/venantvr/Python.Publisher.Subscriber.git
cd Python.Publisher.Subscriber

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -r requirements-dev.txt
pip install -e .
```

### Using Docker

```bash
# Using Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t python.publisher.subscriber:latest .
docker run -p 5000:5000 python.publisher.subscriber:latest
```

## 🚀 Quick Start

### 1. Start the Server

```bash
# Run directly
python src/pubsub_ws.py
```

The server will start on `http://localhost:5000`

### 2. Publish Messages

#### Using curl

```bash
curl -X POST http://localhost:5000/publish \
     -H "Content-Type: application/json" \
     -d '{"topic": "sports", "message": "Goal scored!"}'
```

#### Using Python

```python
import requests

response = requests.post(
    "http://localhost:5000/publish",
    json={"topic": "sports", "message": "Goal scored!"}
)
```

### 3. Subscribe to Topics

#### Using Python Client

```python
from pubsub import PubSubClient

def handle_sports_message(message):
    print(f"Sports update: {message}")

def handle_news_message(message):
    print(f"News update: {message}")

# Create client and connect
client = PubSubClient(
    consumer_name="alice",
    topics=["sports", "news"]
)

# Register message handlers
client.register_handler("sports", handle_sports_message)
client.register_handler("news", handle_news_message)

# Start listening
client.start()
```

#### Using Web Interface

Open your browser at `http://localhost:5000/client.html`

## 📁 Project Structure

```text
Python.Publisher.Subscriber/
├── src/                      # Source code
│   ├── pubsub/              # Core library modules
│   │   ├── __init__.py
│   │   ├── pubsub_client.py
│   │   └── pubsub_message.py
│   ├── pubsub_ws.py         # Main server application
│   └── client.py            # Client implementation
├── tests/                    # Test suite
│   ├── test_pubsub_ws.py
│   └── test_pubsub_client.py
├── config/                   # Configuration files
├── docs/                     # Documentation
├── migrations/               # Database migrations
├── static/                   # Static web files
├── .github/                  # GitHub Actions workflows
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker Compose setup
├── Makefile                 # Development commands
├── pyproject.toml          # Python project configuration
├── setup.py                # Package setup
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🧪 Testing

### Run Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_pubsub_ws.py -v

# Run in watch mode
pytest-watch tests/ -v
```

## 🛠️ Development

### Setup Development Environment

```bash
# Install development dependencies
make install

# Setup pre-commit hooks
pre-commit install

# Format code
make format

# Run all checks
make check
```

### Available Make Commands

```bash
make help         # Show all available commands
make test         # Run tests
make format       # Format code
make check        # Run format and tests
make clean        # Clean generated files
make install      # Install dependencies
make update       # Update dependencies
```

## 📊 Database Schema

The application uses SQLite with the following schema:

### Messages Table

- `id`: Primary key
- `topic`: Message topic
- `message`: Message content
- `timestamp`: Creation time

### Subscriptions Table

- `id`: Primary key
- `consumer`: Consumer name
- `topic`: Subscribed topic
- `timestamp`: Subscription time

### Consumptions Table

- `id`: Primary key
- `consumer`: Consumer name
- `message_id`: Reference to message
- `consumed_at`: Consumption timestamp

## 🔌 API Reference

### REST Endpoints

#### POST /publish

Publish a message to a topic.

```json
{
  "topic": "string",
  "message": "string"
}
```

#### GET /health

Health check endpoint.

### WebSocket Events

#### Client → Server

- `subscribe`: Subscribe to topics

```json
{
  "consumer": "string",
  "topics": ["string"]
}
```

- `publish`: Publish message via WebSocket

```json
{
  "topic": "string",
  "message": "string"
}
```

#### Server → Client

- `message`: Receive subscribed messages
- `client_list`: Updated list of connected clients
- `consumption_update`: Message consumption notifications

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Docker Build

```bash
# Build image
docker build -t python.publisher.subscriber:latest .

# Run container
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/pubsub.db:/app/pubsub.db \
  --name pubsub-server \
  python.publisher.subscriber:latest
```

## 📈 Monitoring

### Health Check

```bash
curl http://localhost:5000/health
```

### Metrics

The application provides real-time metrics through the web interface:

- Connected clients count
- Messages per topic
- Consumption rate
- Active subscriptions

## 🔒 Security

- Input validation on all endpoints
- SQL injection prevention via parameterized queries
- XSS protection in web interface
- Rate limiting support
- CORS configuration available

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Add tests for new features
- Update documentation as needed
- Use type hints
- Run `make pre-commit` before committing

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Flask team for the excellent web framework
- Socket.IO team for real-time communication
- All contributors and users of this project

## 📚 Documentation

Full documentation is available in the `docs/` directory.

## 📧 Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: <venantvr@gmail.com>

## 🗺️ Roadmap

- [ ] Redis backend support
- [ ] Message persistence options
- [ ] Authentication and authorization
- [ ] Message encryption
- [ ] Horizontal scaling support
- [ ] GraphQL API
- [ ] Admin dashboard
- [ ] Message replay functionality
- [ ] Dead letter queue
- [ ] Prometheus metrics export

---

<!-- markdownlint-disable MD033 -->
<div align="center">
Made with ❤️ by the Python Publisher Subscriber team
</div>
