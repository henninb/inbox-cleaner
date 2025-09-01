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
from .analysis import EmailAnalyzer


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
    
    @app.get("/analysis", response_class=HTMLResponse)
    async def analysis_page(request: Request):
        """Email analysis page."""
        return app.state.templates.TemplateResponse(
            request, "analysis.html", {}
        )
    
    @app.get("/api/analysis")
    async def analysis_api():
        """API endpoint for email analysis data."""
        try:
            analyzer = EmailAnalyzer(app.state.db_path)
            
            # Get comprehensive analysis
            stats = analyzer.get_detailed_statistics()
            suspicious = analyzer.detect_suspicious_emails()
            cleanup_recs = analyzer.get_cleanup_recommendations()
            
            return {
                "total_emails": stats.get("total_emails", 0),
                "suspicious_count": len(suspicious),
                "label_distribution": stats.get("label_distribution", {}),
                "domain_distribution": stats.get("domain_distribution", {}),
                "category_breakdown": stats.get("category_breakdown", {}),
                "cleanup_recommendations": {
                    "expired_emails": len(cleanup_recs.get("expired_emails", [])),
                    "spam_candidates": len(cleanup_recs.get("spam_candidates", [])),
                    "bulk_promotional": len(cleanup_recs.get("bulk_promotional", [])),
                    "old_social": len(cleanup_recs.get("old_social", []))
                },
                "time_distribution": stats.get("time_distribution", {}),
                "top_suspicious": suspicious[:10] if suspicious else []
            }
        except Exception as e:
            return {
                "total_emails": 0,
                "suspicious_count": 0,
                "error": str(e)
            }
    
    @app.get("/api/analysis/cleanup")
    async def cleanup_recommendations_api():
        """API endpoint for cleanup recommendations."""
        try:
            analyzer = EmailAnalyzer(app.state.db_path)
            recommendations = analyzer.get_cleanup_recommendations()
            
            # Add summary statistics
            summary = {
                "expired_emails": len(recommendations.get("expired_emails", [])),
                "spam_candidates": len(recommendations.get("spam_candidates", [])),
                "bulk_promotional": len(recommendations.get("bulk_promotional", [])),
                "old_social": len(recommendations.get("old_social", []))
            }
            
            return {
                **recommendations,
                "summary": summary,
                "recommendations": [
                    f"Found {summary['expired_emails']} expired USPS emails ready for deletion",
                    f"Identified {summary['spam_candidates']} suspicious emails for review",
                    f"Found {summary['bulk_promotional']} promotional emails for cleanup",
                    f"Found {summary['old_social']} old social media notifications"
                ]
            }
        except Exception as e:
            return {
                "expired_emails": [],
                "spam_candidates": [],
                "bulk_promotional": [],
                "old_social": [],
                "error": str(e)
            }
    
    @app.get("/api/analysis/suspicious")
    async def suspicious_emails_api(limit: int = Query(50, ge=1, le=500)):
        """API endpoint for suspicious emails."""
        try:
            analyzer = EmailAnalyzer(app.state.db_path)
            suspicious = analyzer.detect_suspicious_emails()
            
            return {
                "suspicious_emails": suspicious[:limit],
                "total_found": len(suspicious),
                "spam_indicators": analyzer.get_spam_indicators()
            }
        except Exception as e:
            return {
                "suspicious_emails": [],
                "total_found": 0,
                "error": str(e)
            }
    
    @app.get("/api/analysis/domains")
    async def domain_analysis_api():
        """API endpoint for domain distribution analysis."""
        try:
            analyzer = EmailAnalyzer(app.state.db_path)
            domain_dist = analyzer.get_domain_distribution()
            
            # Sort by count and get top domains
            sorted_domains = sorted(
                domain_dist.items(), 
                key=lambda x: x[1]["count"], 
                reverse=True
            )
            
            return {
                "total_domains": len(domain_dist),
                "top_domains": dict(sorted_domains[:20]),
                "domain_stats": domain_dist
            }
        except Exception as e:
            return {
                "total_domains": 0,
                "top_domains": {},
                "error": str(e)
            }
    
    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)