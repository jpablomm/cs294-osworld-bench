"""
Storage Manager - Google Cloud Storage Integration

Handles task results and artifacts storage to GCS.
Supports both GCS and local filesystem for development.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages task results and artifacts storage"""

    def __init__(self, bucket_name: Optional[str] = None, use_gcs: bool = True):
        """
        Initialize Storage Manager

        Args:
            bucket_name: GCS bucket name (e.g., 'osworld-results')
            use_gcs: If True, use GCS. If False, use local filesystem.
        """
        self.bucket_name = bucket_name
        self.use_gcs = use_gcs and bucket_name is not None

        if self.use_gcs:
            try:
                from google.cloud import storage
                self.storage_client = storage.Client()
                self.bucket = self.storage_client.bucket(bucket_name)
                logger.info(f"Initialized GCS storage with bucket: {bucket_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize GCS, falling back to local: {e}")
                self.use_gcs = False

        if not self.use_gcs:
            # Use local filesystem in ./orchestrator_results/
            self.local_base_dir = Path("./orchestrator_results")
            self.local_base_dir.mkdir(exist_ok=True)
            logger.info(f"Using local filesystem storage: {self.local_base_dir.absolute()}")

    def save_task_results(self, task_id: str, results: Dict[str, Any]) -> str:
        """
        Save task results as JSON

        Args:
            task_id: Task identifier
            results: Results dictionary

        Returns:
            Storage path/URL
        """
        results_json = json.dumps(results, indent=2)
        path = f"tasks/{task_id}/results.json"

        if self.use_gcs:
            blob = self.bucket.blob(path)
            blob.upload_from_string(results_json, content_type="application/json")
            url = f"gs://{self.bucket_name}/{path}"
            logger.info(f"Saved results to GCS: {url}")
            return url
        else:
            local_path = self.local_base_dir / "tasks" / task_id / "results.json"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(results_json)
            logger.info(f"Saved results to local: {local_path}")
            return str(local_path)

    def get_task_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve task results

        Args:
            task_id: Task identifier

        Returns:
            Results dictionary or None if not found
        """
        path = f"tasks/{task_id}/results.json"

        try:
            if self.use_gcs:
                blob = self.bucket.blob(path)
                if not blob.exists():
                    return None
                results_json = blob.download_as_text()
                return json.loads(results_json)
            else:
                local_path = self.local_base_dir / "tasks" / task_id / "results.json"
                if not local_path.exists():
                    return None
                return json.loads(local_path.read_text())
        except Exception as e:
            logger.error(f"Failed to retrieve results for {task_id}: {e}")
            return None

    def upload_artifacts(
        self,
        task_id: str,
        artifacts_dir: str
    ) -> List[Dict[str, str]]:
        """
        Upload all artifacts from a directory

        Args:
            task_id: Task identifier
            artifacts_dir: Local directory containing artifacts

        Returns:
            List of uploaded artifact info dicts
        """
        artifacts_path = Path(artifacts_dir)
        if not artifacts_path.exists():
            logger.warning(f"Artifacts directory does not exist: {artifacts_dir}")
            return []

        uploaded_artifacts = []
        base_path = f"tasks/{task_id}/artifacts"

        for file_path in artifacts_path.rglob("*"):
            if file_path.is_file():
                # Get relative path from artifacts_dir
                rel_path = file_path.relative_to(artifacts_path)
                storage_path = f"{base_path}/{rel_path}"

                try:
                    if self.use_gcs:
                        blob = self.bucket.blob(storage_path)

                        # Determine content type
                        content_type = self._get_content_type(file_path)

                        # Upload file
                        blob.upload_from_filename(
                            str(file_path),
                            content_type=content_type
                        )
                        url = f"gs://{self.bucket_name}/{storage_path}"
                        logger.debug(f"Uploaded artifact to GCS: {url}")
                    else:
                        local_dest = self.local_base_dir / "tasks" / task_id / "artifacts" / rel_path
                        local_dest.parent.mkdir(parents=True, exist_ok=True)

                        # Copy file
                        import shutil
                        shutil.copy2(file_path, local_dest)
                        url = str(local_dest)
                        logger.debug(f"Copied artifact to local: {url}")

                    uploaded_artifacts.append({
                        "filename": str(rel_path),
                        "url": url,
                        "size_bytes": file_path.stat().st_size,
                    })
                except Exception as e:
                    logger.error(f"Failed to upload {file_path}: {e}")

        logger.info(f"Uploaded {len(uploaded_artifacts)} artifacts for task {task_id}")
        return uploaded_artifacts

    def list_artifacts(self, task_id: str) -> List[Dict[str, str]]:
        """
        List all artifacts for a task

        Args:
            task_id: Task identifier

        Returns:
            List of artifact info dicts
        """
        prefix = f"tasks/{task_id}/artifacts/"
        artifacts = []

        try:
            if self.use_gcs:
                blobs = self.bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    # Get relative filename
                    rel_path = blob.name[len(prefix):]
                    if rel_path:  # Skip directory markers
                        artifacts.append({
                            "filename": rel_path,
                            "url": f"gs://{self.bucket_name}/{blob.name}",
                            "size_bytes": blob.size,
                        })
            else:
                artifacts_dir = self.local_base_dir / "tasks" / task_id / "artifacts"
                if artifacts_dir.exists():
                    for file_path in artifacts_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(artifacts_dir)
                            artifacts.append({
                                "filename": str(rel_path),
                                "url": str(file_path),
                                "size_bytes": file_path.stat().st_size,
                            })
        except Exception as e:
            logger.error(f"Failed to list artifacts for {task_id}: {e}")

        return artifacts

    def delete_task_data(self, task_id: str) -> None:
        """
        Delete all data for a task (results + artifacts)

        Args:
            task_id: Task identifier
        """
        prefix = f"tasks/{task_id}/"

        try:
            if self.use_gcs:
                blobs = self.bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    blob.delete()
                logger.info(f"Deleted all GCS data for task {task_id}")
            else:
                task_dir = self.local_base_dir / "tasks" / task_id
                if task_dir.exists():
                    import shutil
                    shutil.rmtree(task_dir)
                logger.info(f"Deleted all local data for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to delete data for {task_id}: {e}")

    def _get_content_type(self, file_path: Path) -> str:
        """Determine content type from file extension"""
        suffix = file_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".json": "application/json",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".html": "text/html",
            ".xml": "application/xml",
        }
        return content_types.get(suffix, "application/octet-stream")
