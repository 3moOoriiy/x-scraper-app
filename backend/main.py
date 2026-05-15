# =============================================================
# FastAPI Backend - X Posts Scraper API
# =============================================================

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd
import io

from scraper import get_posts, search_posts, _shutdown_driver

app = FastAPI(title="X Posts Scraper API")

# Allow React frontend to call this API.
# Note: when allow_origins=["*"] is used, allow_credentials MUST be False
# otherwise browsers reject the CORS preflight.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",   # matches any origin
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "X Posts Scraper API"}


@app.on_event("shutdown")
def _on_shutdown():
    _shutdown_driver()


ALLOWED_FILTERS = {"all", "24h", "3d", "7d", "30d", "90d", "180d", "365d"}


@app.get("/api/posts")
def fetch_posts(
    username: str = Query(..., description="X username without @"),
    limit: int = Query(10, ge=1, le=2000, description="Number of posts to fetch"),
    date_filter: str = Query("all", description="Relative date filter"),
    specific_date: str | None = Query(None, description="YYYY-MM-DD (single day)"),
    start_date: str | None = Query(None, description="YYYY-MM-DD (range start)"),
    end_date: str | None = Query(None, description="YYYY-MM-DD (range end)"),
):
    """Get latest original posts from a user filtered by date."""
    username = username.strip().lstrip("@")
    if not username:
        return {"error": "Username is required", "posts": []}

    if date_filter not in ALLOWED_FILTERS:
        date_filter = "all"

    return get_posts(
        username, limit=limit, date_filter=date_filter,
        specific_date=specific_date, start_date=start_date, end_date=end_date,
    )


@app.get("/api/search")
def search_endpoint(
    query: str = Query(..., description="Keyword or hashtag"),
    mode: str = Query("keyword", pattern="^(keyword|hashtag)$"),
    limit: int = Query(10, ge=1, le=2000),
    date_filter: str = Query("all"),
    specific_date: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    """Search X for posts by keyword/hashtag."""
    if date_filter not in ALLOWED_FILTERS:
        date_filter = "all"
    return search_posts(
        query, limit=limit, date_filter=date_filter,
        specific_date=specific_date, start_date=start_date, end_date=end_date,
        mode=mode,
    )


@app.get("/api/export")
def export_posts(
    username: str = Query(...),
    limit: int = Query(10, ge=1, le=2000),
    date_filter: str = Query("all"),
    specific_date: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
):
    """Export posts as CSV or Excel file."""
    username = username.strip().lstrip("@")
    if date_filter not in ALLOWED_FILTERS:
        date_filter = "all"
    result = get_posts(
        username, limit=limit, date_filter=date_filter,
        specific_date=specific_date, start_date=start_date, end_date=end_date,
    )
    posts = result.get("posts", [])

    if not posts:
        return {"error": result.get("error") or "No posts found"}

    rows = []
    for p in posts:
        rows.append({
            "Username":      p.get("username", ""),
            "Post_URL":      p.get("post_url", ""),
            "Type":          p.get("post_type", "post"),
            "Caption":       p.get("caption", ""),
            "Likes":         p.get("likes", 0),
            "Retweets":      p.get("retweets", 0),
            "Comments":      p.get("comments", 0),
            "Views":         p.get("views", 0),
            "Has_Video":     p.get("has_video", False),
            "Is_Retweet":    p.get("is_retweet", False),
            "Is_Quote":      p.get("is_quote", False),
            "Quoted_Author": p.get("quoted_author", ""),
            "Quoted_Text":   p.get("quoted_caption", ""),
            "Image_URL":     " | ".join(p.get("image_urls", [])),
            "Video_URL":     " | ".join(p.get("video_urls", [])),
            "Created_At":    p.get("created_at", ""),
        })

    df = pd.DataFrame(rows)

    if format == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=x_posts_{username}.csv"},
        )
    else:
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=x_posts_{username}.xlsx"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
