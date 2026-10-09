from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user, require_role
from audit import write_audit
from ratelimit import SlidingWindowLimiter
import models, schemas

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("", response_model=List[schemas.KBArticleOut])
def list_articles(
    q: Optional[str] = Query(None, description="Full-text search query"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.KBArticle)
    # Drafts awaiting approval are only visible to staff
    if current_user.role not in ("technician", "admin"):
        query = query.filter(models.KBArticle.status == "published")

    if q:
        words = [w.strip() for w in q.split() if len(w.strip()) > 2] or [q.strip()]
        query = query.filter(or_(*[
            or_(models.KBArticle.title.icontains(w), models.KBArticle.body.icontains(w), models.KBArticle.tags.icontains(w))
            for w in words
        ])).limit(20)
        return query.all()
    return query.order_by(models.KBArticle.updated_at.desc()).all()


@router.post("", response_model=schemas.KBArticleOut, status_code=201)
def create_article(
    payload: schemas.KBArticleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin", "technician")),
):
    article = models.KBArticle(**payload.model_dump())
    db.add(article)
    db.commit()
    db.refresh(article)
    write_audit(db, current_user, "kb_article_created", "kb_article", article.id, f"KB article created: '{article.title}'")
    return article


@router.get("/{article_id}", response_model=schemas.KBArticleOut)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    article = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.patch("/{article_id}", response_model=schemas.KBArticleOut)
def update_article(
    article_id: int,
    payload: schemas.KBArticleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin", "technician")),
):
    article = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(article, field, value)
    db.commit()
    db.refresh(article)
    write_audit(db, current_user, "kb_article_updated", "kb_article", article_id, f"KB article updated: '{article.title}'")
    return article


@router.delete("/{article_id}", status_code=204)
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("admin")),
):
    article = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    title = article.title
    db.delete(article)
    db.commit()
    write_audit(db, current_user, "kb_article_deleted", "kb_article", article_id, f"KB article deleted: '{title}'")


# One vote per person per article per day keeps the ranking honest
feedback_votes = SlidingWindowLimiter(max_events=1, window_seconds=24 * 60 * 60)


@router.post("/{article_id}/feedback", status_code=204)
def article_feedback(
    article_id: int,
    payload: schemas.KBFeedback,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """'Was this article helpful?' — feeds the chatbot's knowledge ranking."""
    article = db.query(models.KBArticle).filter(models.KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    key = f"{current_user.id}|{article_id}"
    if feedback_votes.retry_after(key):
        return None  # already voted today; silently ignore repeats
    feedback_votes.hit(key)
    column = models.KBArticle.helpful_count if payload.helpful else models.KBArticle.not_helpful_count
    db.query(models.KBArticle).filter(models.KBArticle.id == article_id).update(
        {column: column + 1}, synchronize_session=False
    )
    db.commit()
    return None
