"""
Snapshot Manager - GCP Disk Snapshot Operations

Handles VM state restoration via disk snapshot replacement.
Used by VMPoolManager to reset VMs between tasks.
"""

import logging
import time
from typing import Optional

from google.cloud import compute_v1

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_ZONE = "us-central1-a"
DEFAULT_SNAPSHOT_NAME = "osworld-golden-snapshot"
DEFAULT_DISK_SIZE_GB = 50
DEFAULT_OPERATION_TIMEOUT = 300


class SnapshotManager:
    """
    Manages GCP disk snapshots for VM state restoration.

    Restores a VM to clean state by:
    1. Stopping the VM
    2. Detaching and deleting the current boot disk
    3. Creating a new boot disk from the golden snapshot
    4. Attaching the new disk and starting the VM
    """

    def __init__(
        self,
        project_id: str,
        zone: str = DEFAULT_ZONE,
        snapshot_name: str = DEFAULT_SNAPSHOT_NAME,
    ):
        """
        Initialize Snapshot Manager.

        Args:
            project_id: GCP project ID
            zone: GCE zone for operations
            snapshot_name: Name of the golden snapshot to restore from
        """
        self.project_id = project_id
        self.zone = zone
        self.snapshot_name = snapshot_name

        # Initialize GCP clients
        self.snapshots_client = compute_v1.SnapshotsClient()
        self.disks_client = compute_v1.DisksClient()
        self.instances_client = compute_v1.InstancesClient()
        self.zone_operations_client = compute_v1.ZoneOperationsClient()
        self.global_operations_client = compute_v1.GlobalOperationsClient()

        logger.info(
            f"SnapshotManager initialized (project={project_id}, "
            f"zone={zone}, snapshot={snapshot_name})"
        )

    def get_snapshot_link(self) -> Optional[str]:
        """
        Get the self_link of the golden snapshot.

        Returns:
            Snapshot self_link URL, or None if not found
        """
        try:
            snapshot = self.snapshots_client.get(
                project=self.project_id,
                snapshot=self.snapshot_name
            )
            logger.info(f"Found snapshot: {self.snapshot_name}")
            return snapshot.self_link
        except Exception as e:
            logger.warning(f"Snapshot '{self.snapshot_name}' not found: {e}")
            return None

    def restore_vm_disk(
        self,
        vm_name: str,
        new_disk_name: str,
        disk_size_gb: int = DEFAULT_DISK_SIZE_GB,
        timeout: int = DEFAULT_OPERATION_TIMEOUT,
    ) -> bool:
        """
        Restore a VM to clean state by replacing its boot disk from snapshot.

        Process:
        1. Stop the VM
        2. Get current boot disk info
        3. Detach the boot disk
        4. Delete the old disk
        5. Create new disk from snapshot
        6. Attach new disk as boot disk
        7. Start the VM

        Args:
            vm_name: Name of the VM to restore
            new_disk_name: Name for the new boot disk
            disk_size_gb: Size of the new disk in GB
            timeout: Timeout for each operation in seconds

        Returns:
            True if restore succeeded, False otherwise
        """
        logger.info(f"Starting disk restore for VM {vm_name}")
        restore_start = time.time()

        try:
            # Step 1: Stop the VM
            logger.info(f"[1/7] Stopping VM {vm_name}...")
            stop_op = self.instances_client.stop(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name
            )
            self._wait_for_zone_operation(stop_op.name, timeout)
            logger.info(f"VM {vm_name} stopped")

            # Step 2: Get current boot disk info
            logger.info(f"[2/7] Getting boot disk info for {vm_name}...")
            instance = self.instances_client.get(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name
            )

            old_disk_name = None
            old_device_name = None
            for disk in instance.disks:
                if disk.boot:
                    # Extract disk name from source URL
                    # Format: projects/.../zones/.../disks/DISK_NAME
                    old_disk_name = disk.source.split("/")[-1]
                    old_device_name = disk.device_name
                    break

            if not old_disk_name:
                raise Exception(f"No boot disk found on VM {vm_name}")

            logger.info(f"Found boot disk: {old_disk_name} (device: {old_device_name})")

            # Step 3: Detach the boot disk
            logger.info(f"[3/7] Detaching disk {old_disk_name}...")
            detach_op = self.instances_client.detach_disk(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name,
                device_name=old_device_name
            )
            self._wait_for_zone_operation(detach_op.name, timeout)
            logger.info(f"Disk {old_disk_name} detached")

            # Step 4: Delete the old disk
            logger.info(f"[4/7] Deleting old disk {old_disk_name}...")
            try:
                delete_op = self.disks_client.delete(
                    project=self.project_id,
                    zone=self.zone,
                    disk=old_disk_name
                )
                self._wait_for_zone_operation(delete_op.name, timeout)
                logger.info(f"Old disk {old_disk_name} deleted")
            except Exception as e:
                # Non-fatal: disk might already be deleted
                logger.warning(f"Could not delete old disk {old_disk_name}: {e}")

            # Step 5: Create new disk from snapshot
            logger.info(f"[5/7] Creating disk {new_disk_name} from snapshot {self.snapshot_name}...")
            new_disk = compute_v1.Disk()
            new_disk.name = new_disk_name
            new_disk.size_gb = disk_size_gb
            new_disk.source_snapshot = (
                f"projects/{self.project_id}/global/snapshots/{self.snapshot_name}"
            )
            new_disk.type_ = f"zones/{self.zone}/diskTypes/pd-standard"

            create_op = self.disks_client.insert(
                project=self.project_id,
                zone=self.zone,
                disk_resource=new_disk
            )
            self._wait_for_zone_operation(create_op.name, timeout)
            logger.info(f"New disk {new_disk_name} created from snapshot")

            # Step 6: Attach new disk as boot disk
            logger.info(f"[6/7] Attaching disk {new_disk_name} to {vm_name}...")
            attached_disk = compute_v1.AttachedDisk()
            attached_disk.source = f"zones/{self.zone}/disks/{new_disk_name}"
            attached_disk.boot = True
            attached_disk.auto_delete = True

            attach_op = self.instances_client.attach_disk(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name,
                attached_disk_resource=attached_disk
            )
            self._wait_for_zone_operation(attach_op.name, timeout)
            logger.info(f"Disk {new_disk_name} attached to {vm_name}")

            # Step 7: Start the VM
            logger.info(f"[7/7] Starting VM {vm_name}...")
            start_op = self.instances_client.start(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name
            )
            self._wait_for_zone_operation(start_op.name, timeout)
            logger.info(f"VM {vm_name} started")

            restore_time = time.time() - restore_start
            logger.info(
                f"VM {vm_name} restore completed in {restore_time:.1f}s "
                f"(new disk: {new_disk_name})"
            )
            return True

        except Exception as e:
            restore_time = time.time() - restore_start
            logger.error(
                f"Failed to restore VM {vm_name} after {restore_time:.1f}s: {e}"
            )
            return False

    def _wait_for_zone_operation(
        self,
        operation_name: str,
        timeout: int = DEFAULT_OPERATION_TIMEOUT,
        poll_interval: int = 2,
    ) -> None:
        """
        Wait for a zone-scoped GCP operation to complete.

        Args:
            operation_name: Name of the operation to wait for
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status polls

        Raises:
            TimeoutError: If operation doesn't complete within timeout
            Exception: If operation fails
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            operation = self.zone_operations_client.get(
                project=self.project_id,
                zone=self.zone,
                operation=operation_name
            )

            if operation.status == compute_v1.Operation.Status.DONE:
                if operation.error:
                    errors = [
                        f"{e.code}: {e.message}"
                        for e in operation.error.errors
                    ]
                    raise Exception(f"Operation failed: {'; '.join(errors)}")
                return

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Operation {operation_name} timed out after {timeout}s"
        )

    def _wait_for_global_operation(
        self,
        operation_name: str,
        timeout: int = DEFAULT_OPERATION_TIMEOUT,
        poll_interval: int = 2,
    ) -> None:
        """
        Wait for a global GCP operation (e.g., snapshot creation) to complete.

        Args:
            operation_name: Name of the operation to wait for
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status polls

        Raises:
            TimeoutError: If operation doesn't complete within timeout
            Exception: If operation fails
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            operation = self.global_operations_client.get(
                project=self.project_id,
                operation=operation_name
            )

            if operation.status == compute_v1.Operation.Status.DONE:
                if operation.error:
                    errors = [
                        f"{e.code}: {e.message}"
                        for e in operation.error.errors
                    ]
                    raise Exception(f"Operation failed: {'; '.join(errors)}")
                return

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Operation {operation_name} timed out after {timeout}s"
        )
