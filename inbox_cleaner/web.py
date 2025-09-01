"""Web interface module for inbox cleaner."""

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import math
from datetime import datetime
from typing import Optional, Dict, Any, List
from .database import DatabaseManager
from .analysis import EmailAnalyzer
from .spam_rules import SpamRuleManager
from .deletion import EmailDeletionManager


# Pydantic models for API requests
class SpamRuleCreate(BaseModel):
    domain: Optional[str] = None
    pattern: Optional[str] = None
    rule_type: str = "domain"  # domain, subject, sender
    action: str = "delete"
    reason: str

class DomainDeletionRequest(BaseModel):
    domain: str
    dry_run: bool = True

class BulkDeletionRequest(BaseModel):
    domains: List[str]
    dry_run: bool = True


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

    # Spam Rules Management Endpoints
    @app.get("/spam-rules", response_class=HTMLResponse)
    async def spam_rules_page(request: Request):
        """Spam rules management page."""
        return app.state.templates.TemplateResponse(
            request, "spam_rules.html", {}
        )

    @app.get("/api/spam-rules")
    async def get_spam_rules():
        """Get all spam rules."""
        try:
            rule_manager = SpamRuleManager()
            rules = rule_manager.get_all_rules()
            stats = rule_manager.get_deletion_stats()

            return {
                "rules": rules,
                "stats": stats
            }
        except Exception as e:
            return {
                "rules": [],
                "stats": {},
                "error": str(e)
            }

    @app.post("/api/spam-rules", status_code=201)
    async def create_spam_rule(rule_data: SpamRuleCreate):
        """Create a new spam rule."""
        try:
            rule_manager = SpamRuleManager()

            if rule_data.rule_type == "domain":
                if not rule_data.domain:
                    raise HTTPException(status_code=400, detail="Domain required for domain rule")
                rule = rule_manager.create_domain_rule(
                    domain=rule_data.domain,
                    action=rule_data.action,
                    reason=rule_data.reason
                )
            elif rule_data.rule_type == "subject":
                if not rule_data.pattern:
                    raise HTTPException(status_code=400, detail="Pattern required for subject rule")
                rule = rule_manager.create_subject_rule(
                    pattern=rule_data.pattern,
                    action=rule_data.action,
                    reason=rule_data.reason
                )
            elif rule_data.rule_type == "sender":
                if not rule_data.pattern:
                    raise HTTPException(status_code=400, detail="Pattern required for sender rule")
                rule = rule_manager.create_sender_rule(
                    sender_pattern=rule_data.pattern,
                    action=rule_data.action,
                    reason=rule_data.reason
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid rule type")

            # Save rules to file
            rule_manager.save_rules()

            return rule

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/spam-rules/{rule_id}")
    async def delete_spam_rule(rule_id: str):
        """Delete a spam rule."""
        try:
            rule_manager = SpamRuleManager()
            success = rule_manager.delete_rule(rule_id)

            if success:
                rule_manager.save_rules()
                return {"success": True, "message": "Rule deleted"}
            else:
                raise HTTPException(status_code=404, detail="Rule not found")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/api/spam-rules/{rule_id}/toggle")
    async def toggle_spam_rule(rule_id: str):
        """Toggle spam rule active/inactive."""
        try:
            rule_manager = SpamRuleManager()
            success = rule_manager.toggle_rule(rule_id)

            if success:
                rule_manager.save_rules()
                rule = rule_manager.get_rule_by_id(rule_id)
                return {"success": True, "rule": rule}
            else:
                raise HTTPException(status_code=404, detail="Rule not found")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Email Deletion Endpoints
    @app.post("/api/delete/domain")
    async def delete_emails_by_domain(deletion_request: DomainDeletionRequest):
        """Delete all emails from a specific domain."""
        try:
            # Initialize deletion manager (without Gmail service for now)
            deleter = EmailDeletionManager(gmail_service=None, db_path=app.state.db_path)

            results = deleter.delete_emails_by_domain(
                domain=deletion_request.domain,
                dry_run=deletion_request.dry_run
            )

            return results

        except Exception as e:
            return {
                "error": str(e),
                "domain": deletion_request.domain,
                "total_found": 0,
                "gmail_deleted": 0,
                "database_deleted": 0
            }

    @app.post("/api/delete/bulk")
    async def bulk_delete_emails(deletion_request: BulkDeletionRequest):
        """Bulk delete emails from multiple domains."""
        try:
            deleter = EmailDeletionManager(gmail_service=None, db_path=app.state.db_path)

            results = deleter.bulk_delete_by_domains(
                domains=deletion_request.domains,
                dry_run=deletion_request.dry_run
            )

            return results

        except Exception as e:
            return {
                "error": str(e),
                "domains": deletion_request.domains,
                "total_found": 0,
                "gmail_deleted": 0,
                "database_deleted": 0
            }

    @app.get("/api/delete/preview/{domain}")
    async def preview_domain_deletion(domain: str):
        """Preview what emails would be deleted from a domain."""
        try:
            deleter = EmailDeletionManager(gmail_service=None, db_path=app.state.db_path)

            preview = deleter.delete_emails_by_domain(domain, dry_run=True)

            return preview

        except Exception as e:
            return {
                "error": str(e),
                "domain": domain,
                "total_found": 0
            }

    @app.get("/api/delete/stats")
    async def get_deletion_statistics():
        """Get statistics about potential deletions."""
        try:
            deleter = EmailDeletionManager(gmail_service=None, db_path=app.state.db_path)

            stats = deleter.get_deletion_statistics()

            return stats

        except Exception as e:
            return {
                "error": str(e),
                "total_emails": 0,
                "total_domains": 0
            }

    @app.post("/api/apply-rule/{rule_id}")
    async def apply_spam_rule(rule_id: str, dry_run: bool = Query(True)):
        """Apply a spam rule to existing emails."""
        try:
            rule_manager = SpamRuleManager()
            rule = rule_manager.get_rule_by_id(rule_id)

            if not rule:
                raise HTTPException(status_code=404, detail="Rule not found")

            deleter = EmailDeletionManager(gmail_service=None, db_path=app.state.db_path)

            results = deleter.delete_emails_by_rule(rule, dry_run=dry_run)

            return results

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)