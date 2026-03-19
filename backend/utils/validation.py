import magic

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_FILES = 100


def validate_mime_type(content: bytes, declared_type: str) -> str | None:
    """Validate file via magic bytes. Returns detected MIME type or None if invalid."""
    detected = magic.from_buffer(content[:2048], mime=True)
    if detected in ALLOWED_MIME_TYPES:
        return detected
    # Fallback to magic byte check
    for sig, mime in MAGIC_BYTES.items():
        if content[:len(sig)] == sig:
            return mime
    return None


def validate_file_size(size: int) -> bool:
    return 0 < size <= MAX_FILE_SIZE
