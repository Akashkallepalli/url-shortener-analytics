from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import string
import random

# Database setup
DATABASE_URL = "sqlite:///./url_shortener.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============ DATABASE MODELS ============

class UrlMapping(Base):
    __tablename__ = "url_mappings"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String(10), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    clicks = relationship("Click", back_populates="url")

class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("url_mappings.id"), nullable=False)
    clicked_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50))
    user_agent = Column(String(255))

    url = relationship("UrlMapping", back_populates="clicks")

# Create tables
Base.metadata.create_all(bind=engine)

# ============ FASTAPI APP ============

app = FastAPI(
    title="URL Shortener Service",
    description="Shorten long URLs and track analytics",
    version="1.0.0"
)

# ============ CONSTANTS ============

BASE62_CHARS = string.digits + string.ascii_letters  # 0-9a-zA-Z

# ============ PYDANTIC MODELS ============

class ShortenRequest(BaseModel):
    original_url: HttpUrl

class ShortenResponse(BaseModel):
    short_code: str
    original_url: str

class StatsResponse(BaseModel):
    short_code: str
    original_url: str
    total_clicks: int
    created_at: datetime

# ============ HELPER FUNCTIONS ============

def generate_short_code(length: int = 7) -> str:
    """Generate random 7-char alphanumeric code"""
    return "".join(random.choice(BASE62_CHARS) for _ in range(length))

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============ API ENDPOINTS ============

@app.get("/")
def root():
    """Welcome endpoint"""
    return {
        "service": "URL Shortener",
        "docs": "http://127.0.0.1:8000/docs",
        "version": "1.0.0"
    }

@app.post("/api/shorten", response_model=ShortenResponse)
def create_short_url(payload: ShortenRequest, db = Depends(get_db)):
    """
    Create a shortened URL
    
    Request: {"original_url": "https://www.example.com"}
    Response: {"short_code": "aB7xK9m", "original_url": "https://www.example.com"}
    """
    original_url = str(payload.original_url)
    
    # Retry up to 5 times if collision occurs
    for attempt in range(5):
        code = generate_short_code()
        url = UrlMapping(original_url=original_url, short_code=code)
        db.add(url)
        try:
            db.commit()
            db.refresh(url)
            return ShortenResponse(
                short_code=url.short_code,
                original_url=url.original_url
            )
        except IntegrityError:
            db.rollback()
            continue
    
    raise HTTPException(
        status_code=500,
        detail="Failed to generate unique short code"
    )

@app.get("/{short_code}")
def redirect_short_code(short_code: str, request: Request, db = Depends(get_db)):
    """
    Redirect to original URL (HTTP 302)
    Records click analytics (IP, User-Agent)
    
    Returns: 302 redirect or 404 if not found
    """
    url = db.query(UrlMapping).filter(
        UrlMapping.short_code == short_code
    ).first()
    
    if not url:
        raise HTTPException(status_code=404, detail="Short code not found")

    # Record click
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    click = Click(
        url_id=url.id,
        ip_address=client_host,
        user_agent=user_agent,
    )
    db.add(click)
    db.commit()

    return RedirectResponse(url=url.original_url, status_code=302)

@app.get("/api/stats/{short_code}", response_model=StatsResponse)
def get_stats(short_code: str, db = Depends(get_db)):
    """
    Get analytics for a short code
    
    Returns: short_code, original_url, total_clicks, created_at
    """
    url = db.query(UrlMapping).filter(
        UrlMapping.short_code == short_code
    ).first()
    
    if not url:
        raise HTTPException(status_code=404, detail="Short code not found")
    
    total_clicks = db.query(Click).filter(Click.url_id == url.id).count()
    
    return StatsResponse(
        short_code=url.short_code,
        original_url=url.original_url,
        total_clicks=total_clicks,
        created_at=url.created_at,
    )