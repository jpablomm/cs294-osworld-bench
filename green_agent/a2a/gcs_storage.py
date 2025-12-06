"""
GCS Storage Utility for Assessment Artifacts

Handles uploading screenshots and other artifacts to Google Cloud Storage.
"""

import logging
from pathlib import Path
from typing import Optional
from google.cloud import storage

logger = logging.getLogger(__name__)

# Configuration
GCS_BUCKET_NAME = "osworld-green-agent-artifacts"
GCS_PUBLIC_URL_BASE = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}"


class GCSStorage:
    """Manages uploads to GCS for assessment artifacts"""

    def __init__(self, bucket_name: str = GCS_BUCKET_NAME):
        """Initialize GCS client and bucket"""
        self.bucket_name = bucket_name
        self.client = None
        self.bucket = None
        self._initialize()

    def _initialize(self):
        """Initialize GCS client (lazy to avoid startup errors)"""
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"GCS storage initialized with bucket: {self.bucket_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize GCS client: {e}")
            logger.warning("Artifacts will only be stored locally")

    def upload_file(
        self,
        local_path: str,
        gcs_path: str,
        content_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload file to GCS

        Args:
            local_path: Path to local file
            gcs_path: Destination path in GCS (e.g., "assess-abc123/step_1.png")
            content_type: Optional MIME type

        Returns:
            Public URL of uploaded file, or None if upload failed
        """
        if not self.bucket:
            logger.warning(f"GCS not initialized, skipping upload of {local_path}")
            return None

        try:
            local_file = Path(local_path)
            if not local_file.exists():
                logger.error(f"Local file not found: {local_path}")
                return None

            # Create blob and upload
            blob = self.bucket.blob(gcs_path)

            # Set content type if provided
            if content_type:
                blob.content_type = content_type
            elif local_file.suffix.lower() == '.png':
                blob.content_type = 'image/png'
            elif local_file.suffix.lower() in ['.jpg', '.jpeg']:
                blob.content_type = 'image/jpeg'

            # Upload file
            blob.upload_from_filename(local_path)

            # Note: Bucket is already public via uniform bucket-level access
            # No need to call blob.make_public() - it would fail with uniform access

            public_url = f"{GCS_PUBLIC_URL_BASE}/{gcs_path}"
            logger.info(f"Uploaded {local_path} to {public_url}")

            return public_url

        except Exception as e:
            logger.error(f"Failed to upload {local_path} to GCS: {e}", exc_info=True)
            return None

    def upload_screenshot(
        self,
        assessment_id: str,
        step_number: int,
        local_path: str
    ) -> Optional[str]:
        """
        Upload screenshot for a specific assessment step

        Args:
            assessment_id: Assessment ID (e.g., "assess-abc123")
            step_number: Step number (1-indexed)
            local_path: Path to screenshot file

        Returns:
            Public URL of uploaded screenshot
        """
        gcs_path = f"{assessment_id}/step_{step_number}.png"
        return self.upload_file(local_path, gcs_path, content_type="image/png")

    def upload_artifact(
        self,
        assessment_id: str,
        artifact_name: str,
        local_path: str
    ) -> Optional[str]:
        """
        Upload arbitrary artifact file

        Args:
            assessment_id: Assessment ID
            artifact_name: Name/path of artifact (e.g., "logs/output.txt")
            local_path: Path to local file

        Returns:
            Public URL of uploaded artifact
        """
        gcs_path = f"{assessment_id}/{artifact_name}"
        return self.upload_file(local_path, gcs_path)

    def delete_assessment_artifacts(self, assessment_id: str):
        """
        Delete all artifacts for an assessment

        Args:
            assessment_id: Assessment ID
        """
        if not self.bucket:
            return

        try:
            prefix = f"{assessment_id}/"
            blobs = self.bucket.list_blobs(prefix=prefix)

            deleted = 0
            for blob in blobs:
                blob.delete()
                deleted += 1

            logger.info(f"Deleted {deleted} artifacts for assessment {assessment_id}")

        except Exception as e:
            logger.error(f"Failed to delete artifacts for {assessment_id}: {e}")


# Global instance
_gcs_storage = None


def get_gcs_storage() -> GCSStorage:
    """Get or create global GCS storage instance"""
    global _gcs_storage
    if _gcs_storage is None:
        _gcs_storage = GCSStorage()
    return _gcs_storage
