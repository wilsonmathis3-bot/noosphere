# Noosphere — Thought Experiment App

A dark-themed web app for sharing thought experiments, ideas, and generated visuals.

## What It Is

- **Submit** a thought experiment with title, description, and optional image
- **Browse** a feed of ideas from others
- **View** full details of any post
- **All stored in SQLite** — no external database needed

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + SQLAlchemy + SQLite |
| Frontend | Vanilla JS (single HTML file, no build step) |
| Styling | Pure CSS, dark theme |

## Deploy to Railway

1. Push this repo to GitHub
2. Go to https://railway.app
3. New Project → Deploy from GitHub repo
4. Select your repo
5. Railway auto-detects Python, installs deps, starts the app
6. Go to Settings → Generate Domain
7. Done — frontend and backend run from the same URL

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard (frontend) |
| GET | `/thoughts` | List all thoughts |
| POST | `/thoughts` | Create new thought (multipart form) |
| GET | `/thoughts/{id}` | Get single thought |
| DELETE | `/thoughts/{id}` | Delete a thought (requires `X-Admin-Token`, see below) |
| GET | `/health` | Health check |

## Run Locally

```bash
pip install -r requirements.txt
python main.py
```

Open http://localhost:8000

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `PORT` | `8000` | Port to listen on (Railway sets this) |
| `DATABASE_PATH` | `./thoughts.db` | SQLite file. Point it at a Railway volume (e.g. `/data/thoughts.db`) or posts are lost on every redeploy |
| `UPLOAD_DIR` | `./uploads` | Where uploaded images are stored (also put this on the volume) |
| `MAX_UPLOAD_MB` | `5` | Max image size; larger uploads get HTTP 413 |
| `ADMIN_TOKEN` | *(unset)* | Enables `DELETE /thoughts/{id}`; send it as the `X-Admin-Token` header. When unset, deleting is disabled |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

CI runs the tests on every push and pull request (`.github/workflows/tests.yml`).

