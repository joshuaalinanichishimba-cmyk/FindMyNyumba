"""
app/core/media_validation.py

Server-side validation for listing media uploads (photos + videos).

Trust nothing the client says: the file extension and the reported
content_type are both spoofable. We read the real first bytes ("magic
numbers") and confirm they match a format we allow; the extension only
disambiguates containers that share bytes (mp4 vs mov).

Checks per file: recognized signature, type matches extension, size within the
per-type cap, non-empty (basic corruption guard).
Checks per batch: 1..20 files.

No system dependencies (no libmagic) — runs identically locally and on Render.

Allowed:  photos JPG/JPEG/PNG/WEBP   videos MP4/MOV/WEBM
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.listing_media import MediaType

# Limits (overridable via Settings if present).
try:
    from app.core.config import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None  # type: ignore


def _cfg(name, default):
    return getattr(settings, name, default) if settings is not None else default


MAX_MEDIA_PER_LISTING = _cfg("MAX_MEDIA_PER_LISTING", 20)
MIN_MEDIA_PER_LISTING = _cfg("MIN_MEDIA_PER_LISTING", 1)
MAX_PHOTO_SIZE_BYTES = _cfg("MAX_PHOTO_SIZE_BYTES", 10 * 1024 * 1024)    # 10 MB
MAX_VIDEO_SIZE_BYTES = _cfg("MAX_VIDEO_SIZE_BYTES", 100 * 1024 * 1024)   # 100 MB

PHOTO_EXTENSIONS = {
    "jpg": (MediaType.PHOTO, "image/jpeg"),
    "jpeg": (MediaType.PHOTO, "image/jpeg"),
    "png": (MediaType.PHOTO, "image/png"),
    "webp": (MediaType.PHOTO, "image/webp"),
}
VIDEO_EXTENSIONS = {
    "mp4": (MediaType.VIDEO, "video/mp4"),
    "mov": (MediaType.VIDEO, "video/quicktime"),
    "webm": (MediaType.VIDEO, "video/webm"),
}
ALLOWED_EXTENSIONS = {**PHOTO_EXTENSIONS, **VIDEO_EXTENSIONS}


class MediaValidationError(ValueError):
    """Raised on validation failure. `message` is safe to show the user."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ValidatedMedia:
    media_type: MediaType   # trust THIS, not the client
    mime_type: str
    extension: str
    size_bytes: int


def _looks_like_jpeg(b: bytes) -> bool:
    return b[:3] == b"\xff\xd8\xff"


def _looks_like_png(b: bytes) -> bool:
    return b[:8] == b"\x89PNG\r\n\x1a\n"


def _looks_like_webp(b: bytes) -> bool:
    return len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP"


def _looks_like_webm(b: bytes) -> bool:
    return b[:4] == b"\x1aE\xdf\xa3"  # EBML (shared with mkv; ext disambiguates)


def _is_iso_bmff(b: bytes) -> bool:
    return len(b) >= 12 and b[4:8] == b"ftyp"  # mp4 / mov


def _sniff_category(data: bytes) -> Optional[MediaType]:
    if _looks_like_jpeg(data) or _looks_like_png(data) or _looks_like_webp(data):
        return MediaType.PHOTO
    if _looks_like_webm(data) or _is_iso_bmff(data):
        return MediaType.VIDEO
    return None


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].strip().lower() if "." in filename else ""


def validate_file(filename: str, data: bytes) -> ValidatedMedia:
    """Validate one file's name + raw bytes. Raises MediaValidationError."""
    ext = _ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise MediaValidationError(
            "unsupported_extension",
            f"'{filename}': unsupported file type. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    declared_type, declared_mime = ALLOWED_EXTENSIONS[ext]

    if not data:
        raise MediaValidationError("empty_file", f"'{filename}' is empty or unreadable.")

    sniffed = _sniff_category(data)
    if sniffed is None:
        raise MediaValidationError(
            "unrecognized_content",
            f"'{filename}' does not match any supported photo or video format "
            f"(it may be corrupted or renamed).",
        )
    if sniffed != declared_type:
        raise MediaValidationError(
            "type_mismatch",
            f"'{filename}' looks like a {sniffed.value} but has a "
            f"{declared_type.value} extension.",
        )

    size = len(data)
    limit = MAX_PHOTO_SIZE_BYTES if sniffed == MediaType.PHOTO else MAX_VIDEO_SIZE_BYTES
    if size > limit:
        raise MediaValidationError(
            "file_too_large",
            f"'{filename}' is {size / 1024 / 1024:.1f}MB; max for a "
            f"{sniffed.value} is {limit / 1024 / 1024:.0f}MB.",
        )

    return ValidatedMedia(sniffed, declared_mime, ext, size)


def validate_added_count(existing_count: int, incoming_count: int) -> None:
    """Reject a batch that would exceed the per-listing max."""
    if incoming_count < 1:
        raise MediaValidationError("no_files", "No files were provided.")
    total = existing_count + incoming_count
    if total > MAX_MEDIA_PER_LISTING:
        raise MediaValidationError(
            "too_many_files",
            f"A listing can have at most {MAX_MEDIA_PER_LISTING} media files "
            f"(this listing already has {existing_count}).",
        )


def ensure_minimum(total_count: int) -> None:
    """Enforce 'at least N files' at publish/create time."""
    if total_count < MIN_MEDIA_PER_LISTING:
        raise MediaValidationError(
            "too_few_files",
            f"At least {MIN_MEDIA_PER_LISTING} media file(s) are required.",
        )
