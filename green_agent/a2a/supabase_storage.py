"""
Supabase Storage helper for uploading screenshots and artifacts
"""
import logging
from typing import Optional
from supabase import create_client, Client

from green_agent.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "screenshots"

# Initialize Supabase client
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get or create Supabase client"""
    global _supabase_client

    if not _supabase_client:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase storage client initialized")

    return _supabase_client


async def upload_screenshot(
    assessment_id: str,
    step: int,
    screenshot_bytes: bytes,
    screenshot_type: str  # "before" or "after"
) -> Optional[str]:
    """
    Upload screenshot to Supabase Storage and return public URL

    Args:
        assessment_id: Assessment ID
        step: Step number
        screenshot_bytes: Screenshot PNG data
        screenshot_type: "before" or "after"

    Returns:
        Public URL of uploaded screenshot, or None if upload failed
    """
    try:
        client = get_supabase_client()

        # Create file path: {assessment_id}/step_{step}_{type}.png
        file_path = f"{assessment_id}/step_{step}_{screenshot_type}.png"

        # Upload to Supabase Storage
        client.storage.from_(STORAGE_BUCKET).upload(
            file_path,
            screenshot_bytes,
            file_options={"content-type": "image/png", "upsert": "true"}
        )

        # Get public URL
        public_url = client.storage.from_(STORAGE_BUCKET).get_public_url(file_path)

        logger.info(f"Uploaded screenshot: {file_path} -> {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Failed to upload screenshot to Supabase: {e}")
        return None


def ensure_bucket_exists():
    """Ensure the screenshots bucket exists (run once during setup)"""
    try:
        client = get_supabase_client()

        # Try to create bucket (will fail if exists, which is fine)
        try:
            client.storage.create_bucket(STORAGE_BUCKET, options={"public": True})
            logger.info(f"Created Supabase storage bucket: {STORAGE_BUCKET}")
        except Exception as e:
            # Bucket likely already exists
            logger.debug(f"Bucket creation skipped (may already exist): {e}")

    except Exception as e:
        logger.error(f"Failed to ensure bucket exists: {e}")
