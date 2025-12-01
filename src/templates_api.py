"""REST API endpoints for template operations."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import TemplateDB
from typedefs import TemplateResponse

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: UUID, db: Session = Depends(get_db)) -> TemplateResponse:
    """Get a specific template by ID.

    Args:
        template_id: UUID of the template to retrieve
        db: Database session

    Returns:
        TemplateResponse with template details

    Raises:
        HTTPException: 404 if template not found
    """
    template = db.query(TemplateDB).filter(TemplateDB.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        exercises=template.exercises,
    )


@router.get("", response_model=List[TemplateResponse])
def list_templates(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> List[TemplateResponse]:
    """List all templates with pagination.

    Args:
        skip: Number of templates to skip (default: 0)
        limit: Maximum number of templates to return (default: 100)
        db: Database session

    Returns:
        List of TemplateResponse objects
    """
    templates = db.query(TemplateDB).offset(skip).limit(limit).all()

    return [
        TemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            exercises=template.exercises,
        )
        for template in templates
    ]
