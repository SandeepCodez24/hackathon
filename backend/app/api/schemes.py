from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.db.scheme_orm import get_all_schemes, get_scheme_by_id, filter_schemes, get_scheme_categories
from app.models.scheme import Scheme, SchemeListResponse

router = APIRouter(prefix="/api/schemes", tags=["schemes"])

@router.get("", response_model=SchemeListResponse)
async def list_schemes(
    category: Optional[str] = Query(None, description="Filter by category"),
    state: Optional[str] = Query(None, description="Filter by state eligibility"),
    occupation: Optional[str] = Query(None, description="Filter by occupation"),
    keyword: Optional[str] = Query(None, description="Search keyword"),
):
    """
    List all government schemes with optional filters.
    Returns scheme name, category, benefit summary, and eligibility overview.
    """
    if category or state or occupation or keyword:
        schemes = await filter_schemes(
            category=category,
            state=state,
            occupation=occupation,
            keyword=keyword,
        )
    else:
        schemes = await get_all_schemes()

    return SchemeListResponse(total=len(schemes), schemes=schemes)

@router.get("/categories", response_model=list[str])
async def list_categories():
    """Get all unique scheme categories."""
    return await get_scheme_categories()

@router.get("/{scheme_id}", response_model=Scheme)
async def get_scheme(scheme_id: str):
    """Get detailed information about a specific scheme."""
    scheme = await get_scheme_by_id(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")
    return scheme
