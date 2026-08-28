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
| DELETE | `/thoughts/{id}` | Delete a thought |
| GET | `/health` | Health check |

## Run Locally

```bash
pip install -r requirements.txt
python main.py
```

Open http://localhost:8000
