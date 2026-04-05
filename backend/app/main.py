from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import papers, ratings, shares, users, podcasts, admin, collections, feed, reference_papers

settings = get_settings()

app = FastAPI(
    title="LitOrbit API",
    version="0.1.0",
    description="Academic research intelligence platform",
)

allowed_origins = ["http://localhost:5173"]
if settings.frontend_url and settings.frontend_url != "http://localhost:5173":
    allowed_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers.router)
app.include_router(ratings.router)
app.include_router(shares.router)
app.include_router(users.router)
app.include_router(podcasts.router)
app.include_router(admin.router)
app.include_router(collections.router)
app.include_router(feed.router)
app.include_router(reference_papers.router)

import logging
logging.getLogger(__name__).info(f"Registered {len(app.routes)} routes")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
