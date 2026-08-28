"""
Noosphere — Thought Experiment App
FastAPI backend with embedded frontend
"""

import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DB_PATH = BASE_DIR / "thoughts.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

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
    allow_credentials=True,
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
    db = SessionLocal()
    try:
        image_path = None
        if image and image.filename:
            ext = Path(image.filename).suffix.lower()
            if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                raise HTTPException(400, "Invalid image format")
            filename = f"{uuid.uuid4().hex}{ext}"
            file_path = UPLOAD_DIR / filename
            with file_path.open("wb") as f:
                shutil.copyfileobj(image.file, f)
            image_path = f"/uploads/{filename}"

        thought = ThoughtDB(
            title=title,
            content=content,
            author=author or "Anonymous",
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
    finally:
        db.close()


@app.get("/thoughts", response_model=List[ThoughtOut])
async def list_thoughts(skip: int = 0, limit: int = 50):
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
async def delete_thought(thought_id: int):
    db = SessionLocal()
    try:
        thought = db.query(ThoughtDB).filter(ThoughtDB.id == thought_id).first()
        if not thought:
            raise HTTPException(404, "Thought not found")
        db.delete(thought)
        db.commit()
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
