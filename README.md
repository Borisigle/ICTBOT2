# Bootstrap FastAPI Backend

A minimal FastAPI backend scaffolded with a modern `src/` layout, environment-driven configuration, structured logging, a background scheduler placeholder, and time conversion utilities. This project is intended to be a starting point for building production-ready APIs.

## Features

- **FastAPI application** served by Uvicorn with a simple health endpoint.
- **`src/` package layout** for clear separation of application code and tooling.
- **Configuration management** using Pydantic Settings with `.env` (dotenv) support for environment-specific values such as API keys and timezone preferences.
- **Structured logging** configuration that can be tuned via environment variables.
- **Background scheduler placeholder** ready to host recurring jobs.
- **Time utilities** to convert Eastern Time (EST/EDT) timestamps into a UTC−3 offset.

## Getting Started

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management

### Installation

1. Clone the repository and switch into the project directory.
2. Install dependencies:

   ```bash
   poetry install
   ```

3. Copy the environment template and adjust values as needed:

   ```bash
   cp .env.example .env
   ```

### Running the Server

Start the development server with Uvicorn:

```bash
poetry run uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. A health check endpoint is provided at `/api/health`.

### Code Style and Tooling

Formatting and linting are provided via Black and Ruff. To run them manually:

```bash
poetry run black src
poetry run ruff check src
```

### Project Layout

```
.
├── .env.example           # Sample environment variables
├── pyproject.toml         # Poetry configuration
├── README.md              # Project documentation
├── src/
│   └── app/
│       ├── api/           # API routers and endpoints
│       ├── core/          # Application configuration, logging, scheduler
│       ├── services/      # Business logic and background jobs
│       └── utils/         # Shared utility helpers
└── tests/                 # (Placeholders for future tests)
```

> **Note:** Tests are not yet implemented; add them under the `tests/` directory as the application grows.

## Configuration Reference

| Variable | Description | Default |
| --- | --- | --- |
| `APP_ENV` | Current environment label (`development`, `staging`, `production`, etc.) | `development` |
| `APP_DEBUG` | Enables FastAPI debug mode | `false` |
| `APP_NAME` | Application display name | `Bootstrap FastAPI Service` |
| `APP_VERSION` | API version tag | `0.1.0` |
| `APP_TIMEZONE` | Default timezone used for display | `America/New_York` |
| `LOG_LEVEL` | Logging verbosity level | `INFO` |
| `SERVICE_API_KEY` | API key used by downstream services | _unset_ |
| `BACKGROUND_POLL_INTERVAL_SECONDS` | Interval for scheduler heartbeat | `300` |

## Background Scheduler Placeholder

An asynchronous scheduler loop is provided under `app.core.scheduler`. It currently emits heartbeat logs at the configured interval and is ready to host additional recurring jobs. Extend `app.services` with domain-specific tasks and register them with the scheduler as needed.

## Time Utilities

Time helpers located in `app.utils.time` simplify Eastern Time (handling EST/EDT automatically) conversions to a fixed UTC−3 offset, useful for downstream integrations that expect that timezone.

## Next Steps

- Add domain-specific routers and services.
- Implement persistence, caching, or messaging layers as required.
- Expand test coverage.
- Containerize the service for deployment.
