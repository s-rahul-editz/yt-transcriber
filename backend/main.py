import json
import sqlite3
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from transcriber import transcribe_video, get_playlist_video_ids, extract_video_id

app = FastAPI(title="YouTube Transcriber")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "cache.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                video_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.commit()


init_db()


class TranscribeRequest(BaseModel):
    url: str


class PlaylistRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
def transcribe(req: TranscribeRequest):
    video_id = extract_video_id(req.url)

    with get_db() as conn:
        row = conn.execute(
            "SELECT data FROM transcripts WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row:
            cached = json.loads(row[0])
            cached["from_cache"] = True
            return cached

    try:
        result = transcribe_video(req.url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    result["from_cache"] = False

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO transcripts (video_id, data) VALUES (?, ?)",
            (video_id, json.dumps(result)),
        )
        conn.commit()

    return result


@app.post("/playlist_ids")
def playlist_ids(req: PlaylistRequest):
    """Fast: just returns video IDs + titles in the playlist, no transcription."""
    try:
        videos = get_playlist_video_ids(req.url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"count": len(videos), "videos": videos}


@app.post("/playlist")
def playlist(req: PlaylistRequest):
    """Slow: transcribes every video in the playlist in one blocking call."""
    try:
        videos = get_playlist_video_ids(req.url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    results = []
    for v in videos:
        try:
            results.append(transcribe(TranscribeRequest(url=v["id"])))
        except HTTPException as e:
            results.append({"video_id": v["id"], "title": v["title"], "error": e.detail})
    return {"count": len(results), "results": results}            )
        """)
        conn.commit()


init_db()


class TranscribeRequest(BaseModel):
    url: str


class PlaylistRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
def transcribe(req: TranscribeRequest):
    video_id = extract_video_id(req.url)

    with get_db() as conn:
        row = conn.execute(
            "SELECT data FROM transcripts WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row:
            return json.loads(row[0])

    try:
        result = transcribe_video(req.url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO transcripts (video_id, data) VALUES (?, ?)",
            (video_id, json.dumps(result)),
        )
        conn.commit()

    return result


@app.post("/playlist")
def playlist(req: PlaylistRequest):
    try:
        ids = get_playlist_video_ids(req.url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    results = []
    for vid in ids:
        try:
            results.append(transcribe(TranscribeRequest(url=vid)))
        except HTTPException as e:
            results.append({"video_id": vid, "error": e.detail})
    return {"count": len(results), "results": results}
