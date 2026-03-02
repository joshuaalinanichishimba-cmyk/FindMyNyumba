from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    total_count: int
    total_pages: int
    current_page: int
    limit: int
    items: List[T]

def paginate(items: List[T], total_count: int, page: int, limit: int) -> dict:
    total_pages = (total_count + limit - 1) // limit
    return {
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "limit": limit,
        "items": items
    }
