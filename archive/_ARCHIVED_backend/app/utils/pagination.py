import math
from typing import Any, Dict
from fastapi import Query
from sqlalchemy.orm import Query as SAQuery

class PaginationParams:
    def __init__(
        self,
        page: int = Query(default=1, ge=1, description='Page number'),
        limit: int = Query(default=20, ge=1, le=100, description='Max 100 per page'),
    ):
        self.page = page
        self.limit = limit
        self.offset = (page - 1) * limit

def paginate(query: SAQuery, params: PaginationParams) -> Dict[str, Any]:
    total = query.count()
    items = query.offset(params.offset).limit(params.limit).all()
    total_pages = math.ceil(total / params.limit) if total > 0 else 0
    return {
        "items": items,
        "page": params.page,
        "total": total,
        "total_pages": total_pages,
        "has_next": params.page < total_pages,
        "has_prev": params.page > 1,
    }
