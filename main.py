import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "articles.db")
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", "120"))

app = FastAPI()
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ---------- Database ----------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                summary TEXT,
                authors TEXT,
                published TEXT,
                guid TEXT UNIQUE,
                fetched_at TEXT NOT NULL,
                read INTEGER DEFAULT 0,
                saved INTEGER DEFAULT 0
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_published ON articles(published)"
        )
        # Migration: add 'saved' column for databases created before this
        # feature existed (Render's disk may already have articles.db).
        existing_cols = [
            row["name"] for row in db.execute("PRAGMA table_info(articles)").fetchall()
        ]
        if "saved" not in existing_cols:
            db.execute("ALTER TABLE articles ADD COLUMN saved INTEGER DEFAULT 0")


def load_feeds():
    with open(FEEDS_PATH, "r") as f:
        return json.load(f)


def clean_summary(raw_summary: str, max_len: int = 400) -> str:
    if not raw_summary:
        return ""
    import re

    text = re.sub("<[^<]+?>", " ", raw_summary)
    text = " ".join(text.split())
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def fetch_all_feeds():
    try:
        feeds = load_feeds()
    except Exception as e:
        print(f"Could not read feeds.json: {e}")
        return

    new_count = 0
    for feed in feeds:
        name = feed.get("name") if isinstance(feed, dict) else None
        url = feed.get("url") if isinstance(feed, dict) else None
        if not name or not url:
            print(f"Skipping malformed entry in feeds.json (needs 'name' and 'url'): {feed}")
            continue

        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            continue

        with get_db() as db:
            for entry in parsed.entries:
                guid = entry.get("id") or entry.get("link")
                if not guid:
                    continue
                title = entry.get("title", "(untitled)")
                link = entry.get("link", "")
                summary = clean_summary(
                    entry.get("summary", "") or entry.get("description", "")
                )
                authors = ""
                if "authors" in entry:
                    authors = ", ".join(
                        a.get("name", "") for a in entry.authors if a.get("name")
                    )
                elif "author" in entry:
                    authors = entry.get("author", "")

                published = ""
                if entry.get("published_parsed"):
                    published = time.strftime(
                        "%Y-%m-%d %H:%M:%S", entry.published_parsed
                    )
                elif entry.get("updated_parsed"):
                    published = time.strftime(
                        "%Y-%m-%d %H:%M:%S", entry.updated_parsed
                    )
                else:
                    published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                try:
                    db.execute(
                        """
                        INSERT INTO articles
                        (journal, title, link, summary, authors, published, guid, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            title,
                            link,
                            summary,
                            authors,
                            published,
                            guid,
                            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    new_count += 1
                except sqlite3.IntegrityError:
                    # already have this article (duplicate guid)
                    pass
    print(f"Feed refresh complete. {new_count} new articles.")


# ---------- Scheduler ----------

scheduler = BackgroundScheduler()


@app.on_event("startup")
def startup():
    init_db()
    try:
        fetch_all_feeds()  # populate immediately on startup
    except Exception as e:
        print(f"Initial feed fetch failed (app will still start): {e}")
    scheduler.add_job(fetch_all_feeds, "interval", minutes=REFRESH_MINUTES)
    scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()


# ---------- Routes ----------

def query_articles(journal=None, unread_only=False, saved_only=False):
    conditions = []
    params = []
    if journal:
        conditions.append("journal = ?")
        params.append(journal)
    if unread_only:
        conditions.append("read = 0")
    if saved_only:
        conditions.append("saved = 1")

    query = "SELECT * FROM articles"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY published DESC LIMIT 200"
    return query, params


def render_feed_page(request: Request, view: str, journal, unread_only, saved_only):
    with get_db() as db:
        query, params = query_articles(journal, unread_only, saved_only)
        articles = db.execute(query, params).fetchall()
        journals = [
            row["journal"]
            for row in db.execute(
                "SELECT DISTINCT journal FROM articles ORDER BY journal"
            ).fetchall()
        ]

    return templates.TemplateResponse(
        "feed.html",
        {
            "request": request,
            "articles": articles,
            "journals": journals,
            "selected_journal": journal,
            "unread_only": unread_only,
            "view": view,
        },
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request, journal: str = None, unread_only: bool = False):
    return render_feed_page(request, "feed", journal, unread_only, False)


@app.get("/library", response_class=HTMLResponse)
def library(request: Request, journal: str = None):
    return render_feed_page(request, "library", journal, False, True)


@app.post("/mark-read/{article_id}")
def mark_read(article_id: int):
    with get_db() as db:
        db.execute("UPDATE articles SET read = 1 WHERE id = ?", (article_id,))
    return {"ok": True}


@app.post("/toggle-save/{article_id}")
def toggle_save(article_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT saved FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if row is None:
            return {"ok": False}
        new_val = 0 if row["saved"] else 1
        db.execute(
            "UPDATE articles SET saved = ? WHERE id = ?", (new_val, article_id)
        )
    return {"ok": True, "saved": bool(new_val)}


@app.post("/refresh")
def manual_refresh(request: Request):
    fetch_all_feeds()
    # Redirect back to wherever the button was clicked from, instead of
    # showing the raw JSON response.
    destination = request.headers.get("referer", "/")
    return RedirectResponse(url=destination, status_code=303)
