"""
Noosphere — Thought Experiment App
FastAPI backend with embedded frontend
"""

import os
import uuid
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, Header, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Override with DATABASE_PATH (e.g. a Railway volume) so posts survive redeploys.
DB_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "thoughts.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

MAX_TITLE_LEN = 200
MAX_AUTHOR_LEN = 100
MAX_CONTENT_LEN = 20_000
MAX_PAGE_SIZE = 100
MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024)
ALLOWED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
# Deleting posts is disabled unless ADMIN_TOKEN is set; callers must then send
# it in the X-Admin-Token header. (Previously anyone could delete any post.)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ─── Database ────────────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ThoughtDB(Base):
    __tablename__ = "thoughts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(100), nullable=False, default="Anonymous")
    image_path = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)

# ─── Pydantic Models ─────────────────────────────────────────────────────────
class ThoughtCreate(BaseModel):
    title: str
    content: str
    author: Optional[str] = "Anonymous"


class ThoughtOut(BaseModel):
    id: int
    title: str
    content: str
    author: str
    image_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(title="Noosphere", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Browsers reject credentialed requests with a wildcard origin, and the
    # API uses no cookies, so credentials stay off.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/thoughts", response_model=ThoughtOut)
async def create_thought(
    title: str = Form(...),
    content: str = Form(...),
    author: Optional[str] = Form("Anonymous"),
    image: Optional[UploadFile] = File(None),
):
    title = title.strip()
    content = content.strip()
    author = (author or "").strip() or "Anonymous"
    if not title or not content:
        raise HTTPException(400, "Title and content are required")
    if len(title) > MAX_TITLE_LEN:
        raise HTTPException(400, f"Title must be at most {MAX_TITLE_LEN} characters")
    if len(author) > MAX_AUTHOR_LEN:
        raise HTTPException(400, f"Author must be at most {MAX_AUTHOR_LEN} characters")
    if len(content) > MAX_CONTENT_LEN:
        raise HTTPException(400, f"Content must be at most {MAX_CONTENT_LEN} characters")

    db = SessionLocal()
    file_path = None
    try:
        image_path = None
        if image and image.filename:
            ext = Path(image.filename).suffix.lower()
            if ext not in ALLOWED_IMAGE_EXTS:
                raise HTTPException(400, "Invalid image format")
            filename = f"{uuid.uuid4().hex}{ext}"
            file_path = UPLOAD_DIR / filename
            written = 0
            with file_path.open("wb") as f:
                while chunk := image.file.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, f"Image larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
                    f.write(chunk)
            image_path = f"/uploads/{filename}"

        thought = ThoughtDB(
            title=title,
            content=content,
            author=author,
            image_path=image_path,
        )
        db.add(thought)
        db.commit()
        db.refresh(thought)

        return ThoughtOut(
            id=thought.id,
            title=thought.title,
            content=thought.content,
            author=thought.author,
            image_url=thought.image_path,
            created_at=thought.created_at,
        )
    except BaseException:
        # Don't leave half-written or orphaned uploads behind on failure.
        if file_path is not None:
            file_path.unlink(missing_ok=True)
        raise
    finally:
        db.close()


@app.get("/thoughts", response_model=List[ThoughtOut])
async def list_thoughts(skip: int = 0, limit: int = 50):
    skip = max(skip, 0)
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    db = SessionLocal()
    try:
        thoughts = (
            db.query(ThoughtDB)
            .order_by(ThoughtDB.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            ThoughtOut(
                id=t.id,
                title=t.title,
                content=t.content,
                author=t.author,
                image_url=t.image_path,
                created_at=t.created_at,
            )
            for t in thoughts
        ]
    finally:
        db.close()


@app.get("/thoughts/{thought_id}", response_model=ThoughtOut)
async def get_thought(thought_id: int):
    db = SessionLocal()
    try:
        thought = db.query(ThoughtDB).filter(ThoughtDB.id == thought_id).first()
        if not thought:
            raise HTTPException(404, "Thought not found")
        return ThoughtOut(
            id=thought.id,
            title=thought.title,
            content=thought.content,
            author=thought.author,
            image_url=thought.image_path,
            created_at=thought.created_at,
        )
    finally:
        db.close()


@app.delete("/thoughts/{thought_id}")
async def delete_thought(thought_id: int, x_admin_token: Optional[str] = Header(None)):
    if not ADMIN_TOKEN:
        raise HTTPException(403, "Deleting is disabled (set ADMIN_TOKEN to enable it)")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "Missing or invalid X-Admin-Token")
    db = SessionLocal()
    try:
        thought = db.query(ThoughtDB).filter(ThoughtDB.id == thought_id).first()
        if not thought:
            raise HTTPException(404, "Thought not found")
        image_path = thought.image_path
        db.delete(thought)
        db.commit()
        if image_path:
            (UPLOAD_DIR / Path(image_path).name).unlink(missing_ok=True)
        return {"deleted": True}
    finally:
        db.close()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─── Serve Frontend ──────────────────────────────────────────────────────────
frontend_html = BASE_DIR / "frontend" / "index.html"

@app.get("/")
async def serve_index():
    if frontend_html.exists():
        return FileResponse(str(frontend_html))
    return {"message": "Noosphere API is running"}


@app.get("/{path:path}")
async def serve_spa(path: str):
    # API routes handled by FastAPI above; serve frontend for everything else
    if frontend_html.exists():
        return FileResponse(str(frontend_html))
    return {"message": "Noosphere API is running"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
