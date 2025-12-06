"""
VM Manager - Google Compute Engine Integration

Manages OSWorld VM lifecycle: creation, monitoring, deletion.
"""

import logging
import time
import requests
from typing import Optional, Dict, Any
from google.cloud import compute_v1

logger = logging.getLogger(__name__)

# VM configuration constants
DEFAULT_PROJECT_ID = None  # Will be auto-detected from environment
DEFAULT_ZONE = "us-central1-a"
DEFAULT_MACHINE_TYPE = "n1-standard-4"
DEFAULT_IMAGE_FAMILY = "osworld-gnome"
DEFAULT_BOOT_DISK_SIZE_GB = 50


class VMManager:
    """Manages OSWorld VM lifecycle on Google Compute Engine"""

    def __init__(
        self,
        project_id: Optional[str] = None,
        zone: str = DEFAULT_ZONE,
        machine_type: str = DEFAULT_MACHINE_TYPE,
        image_family: str = DEFAULT_IMAGE_FAMILY,
    ):
        """
        Initialize VM Manager

        Args:
            project_id: GCP project ID (auto-detected if None)
            zone: GCE zone for VMs
            machine_type: VM machine type
            image_family: Golden image family name
        """
        self.project_id = project_id
        self.zone = zone
        self.machine_type = machine_type
        self.image_family = image_family

        # Initialize Compute Engine clients
        self.instances_client = compute_v1.InstancesClient()
        self.images_client = compute_v1.ImagesClient()

        # Auto-detect project ID if not provided
        if not self.project_id:
            try:
                import google.auth
                _, self.project_id = google.auth.default()
                logger.info(f"Auto-detected GCP project: {self.project_id}")
            except Exception as e:
                logger.warning(f"Could not auto-detect project ID: {e}")
                self.project_id = "unknown"

    def get_vm_name(self, task_id: str) -> str:
        """Generate VM name from task ID"""
        # Use full task_id to ensure uniqueness for concurrent executions
        # Sanitize for GCP naming: lowercase, hyphens instead of underscores
        safe_id = task_id.replace("_", "-").lower()
        return f"osworld-{safe_id}"

    def create_vm(self, task_id: str) -> Dict[str, Any]:
        """
        Create a new OSWorld VM from golden image

        Args:
            task_id: Unique task identifier

        Returns:
            dict with vm_name, vm_ip, and metadata

        Raises:
            Exception if VM creation fails
        """
        vm_name = self.get_vm_name(task_id)
        logger.info(f"Creating VM {vm_name} for task {task_id}")

        try:
            # Get latest image from family
            image = self.images_client.get_from_family(
                project=self.project_id,
                family=self.image_family
            )
            logger.info(f"Using image: {image.name} from family {self.image_family}")

            # Build instance configuration
            machine_type_full = f"zones/{self.zone}/machineTypes/{self.machine_type}"

            instance = compute_v1.Instance()
            instance.name = vm_name
            instance.machine_type = machine_type_full

            # Boot disk from golden image
            disk = compute_v1.AttachedDisk()
            initialize_params = compute_v1.AttachedDiskInitializeParams()
            initialize_params.source_image = image.self_link
            initialize_params.disk_size_gb = DEFAULT_BOOT_DISK_SIZE_GB
            initialize_params.disk_type = f"zones/{self.zone}/diskTypes/pd-standard"
            disk.initialize_params = initialize_params
            disk.auto_delete = True
            disk.boot = True
            instance.disks = [disk]

            # Network configuration (default network with external IP)
            network_interface = compute_v1.NetworkInterface()
            network_interface.name = "nic0"
            network_interface.network = f"projects/{self.project_id}/global/networks/default"

            # Add external IP access
            access_config = compute_v1.AccessConfig()
            access_config.name = "External NAT"
            access_config.type_ = "ONE_TO_ONE_NAT"
            network_interface.access_configs = [access_config]
            instance.network_interfaces = [network_interface]

            # Labels for tracking
            instance.labels = {
                "purpose": "osworld-task",
                "task-id": task_id[:63].replace("_", "-").lower(),  # GCP label length limit
                "managed-by": "orchestrator",
            }

            # Network tags for firewall rules
            instance.tags = compute_v1.Tags(items=["osworld-vm"])

            # Create the VM
            operation = self.instances_client.insert(
                project=self.project_id,
                zone=self.zone,
                instance_resource=instance
            )

            logger.info(f"VM creation initiated: {vm_name}")
            logger.info(f"Waiting for operation {operation.name} to complete...")

            # Wait for creation to complete
            self._wait_for_operation(operation.name)

            # Get VM details to retrieve IP
            vm_instance = self.instances_client.get(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name
            )

            # Extract external IP
            vm_ip = None
            if vm_instance.network_interfaces:
                for config in vm_instance.network_interfaces[0].access_configs:
                    if config.nat_i_p:
                        vm_ip = config.nat_i_p
                        break

            if not vm_ip:
                raise Exception(f"VM {vm_name} created but no external IP found")

            logger.info(f"VM {vm_name} created successfully with IP {vm_ip}")

            return {
                "vm_name": vm_name,
                "vm_ip": vm_ip,
                "zone": self.zone,
                "machine_type": self.machine_type,
                "image": image.name,
            }

        except Exception as e:
            logger.error(f"Failed to create VM {vm_name}: {e}")
            # Attempt cleanup if VM was partially created
            try:
                self.delete_vm(task_id)
            except:
                pass
            raise

    def wait_for_vm_ready(
        self,
        vm_ip: str,
        timeout: int = 120,
        poll_interval: int = 5
    ) -> bool:
        """
        Wait for OSWorld server to be ready on VM

        Args:
            vm_ip: VM external IP address
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            True if server is ready, False if timeout
        """
        logger.info(f"Waiting for OSWorld server on {vm_ip} to be ready...")
        start_time = time.time()
        osworld_url = f"http://{vm_ip}:5000"

        while time.time() - start_time < timeout:
            try:
                # Try to hit the /platform endpoint
                response = requests.get(
                    f"{osworld_url}/platform",
                    timeout=5
                )
                if response.status_code == 200:
                    platform = response.text.strip().strip('"')
                    logger.info(f"OSWorld server ready on {vm_ip} (platform: {platform})")
                    return True
            except Exception as e:
                elapsed = int(time.time() - start_time)
                logger.debug(f"Server not ready yet ({elapsed}s elapsed): {e}")

            time.sleep(poll_interval)

        logger.error(f"Timeout waiting for OSWorld server on {vm_ip}")
        return False

    def delete_vm(self, task_id: str) -> None:
        """
        Delete OSWorld VM

        Args:
            task_id: Task identifier used to create VM
        """
        vm_name = self.get_vm_name(task_id)
        logger.info(f"Deleting VM {vm_name}")

        try:
            operation = self.instances_client.delete(
                project=self.project_id,
                zone=self.zone,
                instance=vm_name
            )
            logger.info(f"VM deletion initiated: {vm_name}")

            # Wait for deletion to complete
            self._wait_for_operation(operation.name)

            logger.info(f"VM {vm_name} deleted successfully")

        except Exception as e:
            # Don't fail if VM doesn't exist
            if "was not found" in str(e).lower():
                logger.warning(f"VM {vm_name} not found, assuming already deleted")
            else:
                logger.error(f"Failed to delete VM {vm_name}: {e}")
                raise

    def get_vm_cost(self, runtime_seconds: float) -> float:
        """
        Estimate VM cost based on runtime

        Args:
            runtime_seconds: VM runtime in seconds

        Returns:
            Estimated cost in USD
        """
        # n1-standard-4 pricing: ~$0.19/hour
        hourly_rate = 0.19
        hours = runtime_seconds / 3600.0
        return hours * hourly_rate

    def _wait_for_operation(
        self,
        operation_name: str,
        timeout: int = 300
    ) -> None:
        """
        Wait for a GCE zone operation to complete

        Args:
            operation_name: Operation name
            timeout: Max seconds to wait

        Raises:
            Exception if operation fails or times out
        """
        operations_client = compute_v1.ZoneOperationsClient()
        start_time = time.time()

        while time.time() - start_time < timeout:
            operation = operations_client.get(
                project=self.project_id,
                zone=self.zone,
                operation=operation_name
            )

            if operation.status == compute_v1.Operation.Status.DONE:
                if operation.error:
                    error_messages = [
                        f"{error.code}: {error.message}"
                        for error in operation.error.errors
                    ]
                    raise Exception(f"Operation failed: {'; '.join(error_messages)}")
                logger.info(f"Operation {operation_name} completed successfully")
                return

            time.sleep(2)

        raise Exception(f"Operation {operation_name} timed out after {timeout}s")
