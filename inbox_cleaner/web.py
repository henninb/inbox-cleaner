"""Web interface module for inbox cleaner."""

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import math
from datetime import datetime
from typing import Optional, Dict, Any, List
from .database import DatabaseManager


def create_app(db_path: str = "./inbox_cleaner.db") -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Gmail Inbox Cleaner", 
        description="Privacy-focused email management with AI assistance",
        version="0.1.0"
    )
    
    # Store database path in app state
    app.state.db_path = db_path
    
    # Set up templates directory
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))
    
    # Store templates in app state for access in route handlers
    app.state.templates = templates
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.get("/", response_class=RedirectResponse)
    async def root():
        """Redirect root to dashboard."""
        return RedirectResponse(url="/dashboard", status_code=302)
    
    @app.get("/api/emails")
    async def list_emails(
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=1000)
    ):
        """API endpoint to list emails with pagination."""
        try:
            with DatabaseManager(app.state.db_path) as db:
                # Get total count
                stats = db.get_statistics()
                total = stats.get('total_emails', 0)
                
                # Get emails with pagination
                emails = db.get_emails_paginated(page=page, per_page=per_page)
                
                # Format dates for frontend
                for email in emails:
                    if email.get('date_received'):
                        try:
                            # Parse and reformat datetime
                            dt = datetime.fromisoformat(email['date_received'].replace('Z', '+00:00'))
                            email['date_received'] = dt.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, AttributeError):
                            email['date_received'] = str(email['date_received'])
                
                return {
                    "emails": emails,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": math.ceil(total / per_page) if total > 0 else 1
                }
        except Exception as e:
            return {
                "emails": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 1,
                "error": str(e)
            }
    
    @app.get("/api/emails/search")
    async def search_emails(
        q: str = Query(""),
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=1000)
    ):
        """API endpoint to search emails."""
        try:
            with DatabaseManager(app.state.db_path) as db:
                if not q.strip():
                    return {
                        "emails": [],
                        "total": 0,
                        "page": page,
                        "per_page": per_page,
                        "query": q,
                        "total_pages": 1
                    }
                
                # Search emails
                emails = db.search_emails(q, page=page, per_page=per_page)
                total = db.count_search_results(q)
                
                # Format dates for frontend
                for email in emails:
                    if email.get('date_received'):
                        try:
                            dt = datetime.fromisoformat(email['date_received'].replace('Z', '+00:00'))
                            email['date_received'] = dt.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, AttributeError):
                            email['date_received'] = str(email['date_received'])
                
                return {
                    "emails": emails,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "query": q,
                    "total_pages": math.ceil(total / per_page) if total > 0 else 1
                }
        except Exception as e:
            return {
                "emails": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "query": q,
                "total_pages": 1,
                "error": str(e)
            }
    
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Dashboard page showing email statistics."""
        try:
            with DatabaseManager(app.state.db_path) as db:
                stats = db.get_statistics()
        except Exception:
            stats = {"total_emails": 0}
        
        return app.state.templates.TemplateResponse(
            request, "dashboard.html", {"stats": stats}
        )
    
    @app.get("/emails", response_class=HTMLResponse)
    async def email_list_page(request: Request):
        """Email list page with pagination."""
        return app.state.templates.TemplateResponse(
            request, "emails.html", {}
        )
    
    @app.get("/search", response_class=HTMLResponse)
    async def search_page(request: Request):
        """Search page for finding emails."""
        return app.state.templates.TemplateResponse(
            request, "search.html", {}
        )
    
    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)