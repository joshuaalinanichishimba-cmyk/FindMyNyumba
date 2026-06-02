"""app/models/__init__.py - Export all models for easier imports."""
from app.models.user import User
from app.models.listing import Listing
from app.models.saved_listing import SavedListing
from app.models.report import Report
from app.models.listing_media import ListingMedia

__all__ = [
    "User",
    "Listing",
    "SavedListing",
    "Report",
    "ListingMedia",
]
