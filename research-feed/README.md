# Reading Room — your personal research feed

A small web app that checks your chosen journals' RSS feeds on a schedule
and shows new articles as a scrollable feed, Twitter-style. Tap a headline
to open the article/PDF on the publisher's site.

## What's inside
- `main.py` — the app (FastAPI). Fetches feeds, stores articles in a local
  SQLite database (`articles.db`, created automatically), refreshes on a
  timer, and serves the feed page.
- `feeds.json` — your list of journals and their RSS feed URLs. Edit this
  file to add, remove, or fix feeds.
- `templates/feed.html` — the page you see in the browser.
- `requirements.txt` — Python packages needed.
- `render.yaml` — one-click config for deploying on Render.

## 1. Try it on your own computer first (optional but recommended)

You'll need Python 3.10+.

```bash
cd research-feed
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser. The app fetches all
feeds once on startup, so give it a few seconds the first time.

## 2. Fix the two reconstructed feed URLs

Two of your six feeds (Reading Research Quarterly and American Journal of
Evaluation) had their exact RSS URL cut off in the PDFs you shared, so
`feeds.json` currently has my best reconstruction. To get the exact URL:

1. Open the journal's RSS/table-of-contents page in your browser (the
   page that shows the raw XML, like the ones you saved as PDFs).
2. Copy the full URL from the address bar.
3. Paste it into `feeds.json`, replacing the existing `url` value for
   that journal.

If a feed URL is ever wrong, the app just won't show new articles for
that journal — nothing breaks.

## 3. Deploy for free so your phone can reach it anywhere

**Using Render (recommended, and `render.yaml` is already set up for it):**

1. Create a free account at [render.com](https://render.com).
2. Put this project in a GitHub repository (Render deploys from GitHub).
   - If you don't already use GitHub: create a free account at
     [github.com](https://github.com), create a new repository, and
     upload these files to it (GitHub's web upload works fine — no
     command line needed).
3. In Render, click **New +** → **Blueprint**, and point it at your
   GitHub repo. Render will read `render.yaml` and set everything up
   automatically.
4. Click **Deploy**. After a minute or two you'll get a URL like
   `https://research-feed.onrender.com`.

**On your phone:** open that URL in Safari or Chrome, then use
"Add to Home Screen" (Safari: Share button → Add to Home Screen; Chrome:
⋮ menu → Add to Home Screen). It'll now sit on your home screen like an app.

**On your desktop:** just bookmark the same URL.

> Note: Render's free tier "sleeps" after 15 minutes of no traffic, and
> takes ~30 seconds to wake up on your next visit. The background feed
> refresh only runs while the app is awake. If that's a problem, Render's
> cheapest paid tier ($7/mo) keeps it always on — or ask me and I can
> help you set this up on a different free host with different tradeoffs.

## 4. Customize

- **Change how often it checks feeds:** edit `REFRESH_MINUTES` in
  `render.yaml` (or as an environment variable in Render's dashboard).
- **Add more journals:** add another `{"name": ..., "url": ...}` entry to
  `feeds.json`.
- **Force an immediate check:** click "Refresh now" at the top of the
  feed page.
