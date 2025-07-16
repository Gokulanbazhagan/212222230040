# main.py

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, AnyHttpUrl
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import re

app = FastAPI(title="URL Shortener Microservice")

urls_db: Dict[str, dict] = {}
clicks_db: Dict[str, List[dict]] = {}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    print(f"Completed response: {response.status_code}")
    return response

class ShortenRequest(BaseModel):
    url: AnyHttpUrl
    validity: Optional[int] = 30  # in minutes
    shortcode: Optional[str] = None

class ShortenResponse(BaseModel):
    shortLink: str
    expiry: str

class StatsResponse(BaseModel):
    originalUrl: str
    createdAt: str
    expiry: str
    clickCount: int
    clicks: List[dict]

@app.post("/shorturls", response_model=ShortenResponse, status_code=201)
def create_short_url(req: ShortenRequest):
    shortcode = req.shortcode or uuid4().hex[:6]
    if not re.match(r'^[a-zA-Z0-9]{4,}$', shortcode):
        raise HTTPException(status_code=400, detail="Invalid shortcode format.")
    if shortcode in urls_db:
        raise HTTPException(status_code=409, detail="Shortcode already exists.")
    
    expiry = datetime.utcnow() + timedelta(minutes=req.validity)
    urls_db[shortcode] = {
        "original_url": req.url,
        "created_at": datetime.utcnow(),
        "expiry": expiry
    }
    clicks_db[shortcode] = []
    
    return ShortenResponse(
        shortLink=f"http://localhost:8000/{shortcode}",
        expiry=expiry.isoformat() + "Z"
    )

@app.get("/{shortcode}")
def redirect(shortcode: str, request: Request):
    if shortcode not in urls_db:
        raise HTTPException(status_code=404, detail="Shortcode not found.")
    url_entry = urls_db[shortcode]
    if datetime.utcnow() > url_entry["expiry"]:
        raise HTTPException(status_code=410, detail="Link expired.")
    
    clicks_db[shortcode].append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "referrer": request.headers.get("referer"),
        "ip": request.client.host
    })
    return RedirectResponse(url_entry["original_url"])

@app.get("/shorturls/{shortcode}", response_model=StatsResponse)
def stats(shortcode: str):
    if shortcode not in urls_db:
        raise HTTPException(status_code=404, detail="Shortcode not found.")
    url_entry = urls_db[shortcode]
    clicks = clicks_db[shortcode]
    return StatsResponse(
        originalUrl=url_entry["original_url"],
        createdAt=url_entry["created_at"].isoformat() + "Z",
        expiry=url_entry["expiry"].isoformat() + "Z",
        clickCount=len(clicks),
        clicks=clicks
    )
