"""
VM Pool Manager - Reusable VM Pool with Snapshot-Based Reset

Manages a pool of VMs that are reused across tasks via snapshot restoration.
Optimized for sequential batch processing where one VM processes many tasks.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from .snapshot_manager import SnapshotManager
from .vm_manager import VMManager

logger = logging.getLogger(__name__)


class VMState(Enum):
    """VM lifecycle states"""

    CREATING = "creating"  # VM being provisioned
    AVAILABLE = "available"  # Ready for task assignment
    IN_USE = "in_use"  # Currently executing a task
    RESTORING = "restoring"  # Being reset via snapshot
    FAILED = "failed"  # Marked as unhealthy
    DELETED = "deleted"  # Removed from pool


@dataclass
class PooledVM:
    """Represents a VM in the pool"""

    vm_id: str  # Unique pool identifier (pool-vm-0, pool-vm-1, etc.)
    vm_name: str  # GCP instance name
    vm_ip: Optional[str] = None
    state: VMState = VMState.CREATING
    current_task_id: Optional[str] = None
    tasks_completed: int = 0
    consecutive_failures: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    last_restored_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize VM state for monitoring/logging"""
        return {
            "vm_id": self.vm_id,
            "vm_name": self.vm_name,
            "vm_ip": self.vm_ip,
            "state": self.state.value,
            "current_task_id": self.current_task_id,
            "tasks_completed": self.tasks_completed,
            "consecutive_failures": self.consecutive_failures,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "last_restored_at": (
                self.last_restored_at.isoformat() if self.last_restored_at else None
            ),
        }


class VMPoolManager:
    """
    Manages a pool of reusable VMs with snapshot-based state reset.

    Optimized for sequential batch processing where a single VM
    processes multiple tasks with snapshot restore between each.

    Usage:
        pool = VMPoolManager(project_id="my-project", pool_size=1)
        await pool.initialize()

        # Acquire VM for task
        vm = await pool.acquire_vm("task-123")

        # ... execute task on vm.vm_ip ...

        # Release VM back to pool (triggers snapshot restore)
        await pool.release_vm(vm.vm_id, success=True)

        # Cleanup on shutdown
        await pool.shutdown()
    """

    def __init__(
        self,
        project_id: str,
        zone: str = "us-central1-a",
        pool_size: int = 1,
        snapshot_name: str = "osworld-golden-snapshot",
        machine_type: str = "n1-standard-4",
        image_family: str = "osworld-gnome",
        max_tasks_per_vm: int = 50,
        max_consecutive_failures: int = 3,
        restore_timeout: int = 180,
        ready_timeout: int = 300,
        fallback_to_fresh: bool = True,
    ):
        """
        Initialize VM Pool Manager.

        Args:
            project_id: GCP project ID
            zone: GCE zone for VMs
            pool_size: Number of VMs in pool (1 for sequential batch)
            snapshot_name: Name of golden snapshot to restore from
            machine_type: GCE machine type
            image_family: Golden image family for initial VM creation
            max_tasks_per_vm: Recreate VM after this many tasks
            max_consecutive_failures: Mark VM failed after this many failures
            restore_timeout: Timeout for snapshot restore operation
            ready_timeout: Timeout waiting for OSWorld server
            fallback_to_fresh: Create fresh VM if restore fails
        """
        self.project_id = project_id
        self.zone = zone
        self.pool_size = pool_size
        self.snapshot_name = snapshot_name
        self.machine_type = machine_type
        self.image_family = image_family
        self.max_tasks_per_vm = max_tasks_per_vm
        self.max_consecutive_failures = max_consecutive_failures
        self.restore_timeout = restore_timeout
        self.ready_timeout = ready_timeout
        self.fallback_to_fresh = fallback_to_fresh

        # Pool state
        self._vms: Dict[str, PooledVM] = {}
        self._pool_lock = asyncio.Lock()
        self._initialized = False

        # Managers
        self._vm_manager = VMManager(
            project_id=project_id,
            zone=zone,
            machine_type=machine_type,
            image_family=image_family,
        )
        self._snapshot_manager = SnapshotManager(
            project_id=project_id,
            zone=zone,
            snapshot_name=snapshot_name,
        )

        # Stats
        self._stats = {
            "tasks_completed": 0,
            "vms_created": 0,
            "vms_restored": 0,
            "restore_failures": 0,
            "fallback_creations": 0,
        }

        logger.info(
            f"VMPoolManager initialized (project={project_id}, "
            f"pool_size={pool_size}, snapshot={snapshot_name})"
        )

    async def initialize(self) -> None:
        """
        Initialize the VM pool.

        Creates pool_size VMs and waits for them to be ready.
        Verifies that the golden snapshot exists before proceeding.

        Raises:
            RuntimeError: If snapshot not found or no VMs could be created
        """
        if self._initialized:
            logger.warning("Pool already initialized")
            return

        logger.info(f"Initializing VM pool with {self.pool_size} VM(s)...")

        # Verify snapshot exists
        snapshot_link = await asyncio.to_thread(
            self._snapshot_manager.get_snapshot_link
        )
        if not snapshot_link:
            raise RuntimeError(
                f"Golden snapshot '{self.snapshot_name}' not found. "
                "Create it first before enabling VM pool."
            )

        logger.info(f"Verified snapshot exists: {self.snapshot_name}")

        # Create VMs (sequentially for pool_size=1, parallel for larger pools)
        if self.pool_size == 1:
            # Sequential for single VM
            try:
                await self._create_pool_vm("pool-vm-0")
            except Exception as e:
                raise RuntimeError(f"Failed to create pool VM: {e}")
        else:
            # Parallel for multiple VMs
            create_tasks = []
            for i in range(self.pool_size):
                vm_id = f"pool-vm-{i}"
                create_tasks.append(self._create_pool_vm(vm_id))

            results = await asyncio.gather(*create_tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))

            if success_count == 0:
                raise RuntimeError("Failed to create any pool VMs")

            logger.info(
                f"Created {success_count}/{self.pool_size} pool VMs"
            )

        self._initialized = True
        logger.info("VM pool initialization complete")

    async def _create_pool_vm(self, vm_id: str) -> PooledVM:
        """
        Create a new VM for the pool.

        Args:
            vm_id: Unique identifier for this pool slot

        Returns:
            PooledVM instance

        Raises:
            Exception: If VM creation fails
        """
        vm = PooledVM(
            vm_id=vm_id,
            vm_name=f"osworld-{vm_id}",
            state=VMState.CREATING,
        )

        async with self._pool_lock:
            self._vms[vm_id] = vm

        try:
            logger.info(f"Creating pool VM {vm_id}...")

            # Create VM from golden image
            vm_info = await asyncio.to_thread(
                self._vm_manager.create_vm,
                vm_id,
            )

            vm.vm_name = vm_info["vm_name"]
            vm.vm_ip = vm_info["vm_ip"]

            # Wait for OSWorld server to be ready
            logger.info(f"Waiting for OSWorld server on {vm.vm_ip}...")
            ready = await asyncio.to_thread(
                self._vm_manager.wait_for_vm_ready,
                vm.vm_ip,
                timeout=self.ready_timeout,
            )

            if not ready:
                raise TimeoutError(
                    f"VM {vm_id} OSWorld server failed to become ready"
                )

            vm.state = VMState.AVAILABLE
            self._stats["vms_created"] += 1

            logger.info(f"Pool VM {vm_id} ready at {vm.vm_ip}")
            return vm

        except Exception as e:
            logger.error(f"Failed to create pool VM {vm_id}: {e}")
            async with self._pool_lock:
                vm.state = VMState.FAILED
            raise

    async def acquire_vm(
        self,
        task_id: str,
        timeout: float = 300,
    ) -> PooledVM:
        """
        Acquire an available VM from the pool.

        Blocks until a VM is available or timeout is reached.

        Args:
            task_id: ID of the task requesting the VM
            timeout: Max seconds to wait for available VM

        Returns:
            PooledVM assigned to the task

        Raises:
            TimeoutError: If no VM becomes available within timeout
        """
        start_time = time.time()
        poll_interval = 1.0

        while time.time() - start_time < timeout:
            async with self._pool_lock:
                # Find an available VM
                for vm in self._vms.values():
                    if vm.state == VMState.AVAILABLE:
                        vm.state = VMState.IN_USE
                        vm.current_task_id = task_id
                        vm.last_used_at = datetime.utcnow()

                        logger.info(
                            f"Acquired VM {vm.vm_id} for task {task_id} "
                            f"(ip={vm.vm_ip}, tasks_completed={vm.tasks_completed})"
                        )
                        return vm

            # No VM available, wait and retry
            await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"No VM available within {timeout}s for task {task_id}"
        )

    async def release_vm(
        self,
        vm_id: str,
        success: bool = True,
        force_recreate: bool = False,
    ) -> None:
        """
        Release a VM back to the pool after task completion.

        Triggers snapshot restore to return VM to clean state.

        Args:
            vm_id: ID of the VM to release
            success: Whether the task completed successfully
            force_recreate: Force VM recreation instead of restore
        """
        async with self._pool_lock:
            vm = self._vms.get(vm_id)
            if not vm:
                logger.warning(f"VM {vm_id} not found in pool")
                return

            if vm.state != VMState.IN_USE:
                logger.warning(
                    f"VM {vm_id} not in use (state: {vm.state.value})"
                )
                return

            old_task_id = vm.current_task_id
            vm.current_task_id = None
            vm.tasks_completed += 1
            self._stats["tasks_completed"] += 1

            if success:
                vm.consecutive_failures = 0
            else:
                vm.consecutive_failures += 1

            logger.info(
                f"Releasing VM {vm_id} (task={old_task_id}, success={success}, "
                f"total_tasks={vm.tasks_completed}, failures={vm.consecutive_failures})"
            )

        # Decide whether to restore or recreate
        should_recreate = (
            force_recreate
            or vm.consecutive_failures >= self.max_consecutive_failures
            or vm.tasks_completed >= self.max_tasks_per_vm
        )

        if should_recreate:
            reason = "forced" if force_recreate else "threshold_reached"
            await self._recreate_vm(vm_id, reason=reason)
        else:
            await self._restore_vm(vm_id)

    async def _restore_vm(self, vm_id: str) -> None:
        """
        Restore VM to clean state via snapshot.

        Args:
            vm_id: ID of the VM to restore
        """
        async with self._pool_lock:
            vm = self._vms.get(vm_id)
            if not vm:
                return
            vm.state = VMState.RESTORING

        logger.info(f"Restoring VM {vm_id} via snapshot...")
        restore_start = time.time()

        try:
            # Generate unique disk name with timestamp
            new_disk_name = f"{vm.vm_name}-disk-{int(time.time())}"

            # Perform snapshot restore
            success = await asyncio.to_thread(
                self._snapshot_manager.restore_vm_disk,
                vm.vm_name,
                new_disk_name,
                timeout=self.restore_timeout,
            )

            if not success:
                raise Exception("Snapshot restore returned false")

            # Wait for OSWorld server to be ready
            logger.info(f"Waiting for OSWorld server on {vm.vm_ip}...")
            ready = await asyncio.to_thread(
                self._vm_manager.wait_for_vm_ready,
                vm.vm_ip,
                timeout=self.ready_timeout,
            )

            if not ready:
                raise TimeoutError("OSWorld server not ready after restore")

            async with self._pool_lock:
                vm.state = VMState.AVAILABLE
                vm.last_restored_at = datetime.utcnow()

            restore_time = time.time() - restore_start
            self._stats["vms_restored"] += 1

            logger.info(
                f"VM {vm_id} restored in {restore_time:.1f}s "
                f"(total restores: {self._stats['vms_restored']})"
            )

        except Exception as e:
            restore_time = time.time() - restore_start
            logger.error(
                f"Failed to restore VM {vm_id} after {restore_time:.1f}s: {e}"
            )
            self._stats["restore_failures"] += 1

            if self.fallback_to_fresh:
                logger.info(f"Falling back to fresh VM creation for {vm_id}")
                await self._recreate_vm(vm_id, reason="restore_failed")
            else:
                async with self._pool_lock:
                    vm.state = VMState.FAILED

    async def _recreate_vm(self, vm_id: str, reason: str = "unknown") -> None:
        """
        Delete and recreate a VM.

        Args:
            vm_id: ID of the VM to recreate
            reason: Reason for recreation (for logging)
        """
        async with self._pool_lock:
            vm = self._vms.get(vm_id)
            if not vm:
                return

        logger.info(f"Recreating VM {vm_id} (reason: {reason})...")

        # Delete old VM
        try:
            await asyncio.to_thread(
                self._vm_manager.delete_vm,
                vm_id,
            )
            logger.info(f"Old VM {vm_id} deleted")
        except Exception as e:
            logger.warning(f"Failed to delete old VM {vm_id}: {e}")

        # Create new VM
        try:
            # Reset VM state for recreation
            async with self._pool_lock:
                vm.state = VMState.CREATING
                vm.tasks_completed = 0
                vm.consecutive_failures = 0

            await self._create_pool_vm(vm_id)
            self._stats["fallback_creations"] += 1

            logger.info(f"VM {vm_id} recreated successfully")

        except Exception as e:
            logger.error(f"Failed to recreate VM {vm_id}: {e}")
            async with self._pool_lock:
                if vm_id in self._vms:
                    self._vms[vm_id].state = VMState.FAILED

    async def shutdown(self) -> None:
        """
        Shutdown the pool and delete all VMs.

        Should be called on application shutdown for cleanup.
        """
        logger.info("Shutting down VM pool...")

        async with self._pool_lock:
            vm_ids = list(self._vms.keys())

        if not vm_ids:
            logger.info("No VMs to clean up")
            return

        # Delete all VMs
        for vm_id in vm_ids:
            try:
                logger.info(f"Deleting pool VM {vm_id}...")
                await asyncio.to_thread(
                    self._vm_manager.delete_vm,
                    vm_id,
                )
                async with self._pool_lock:
                    if vm_id in self._vms:
                        self._vms[vm_id].state = VMState.DELETED
                logger.info(f"Pool VM {vm_id} deleted")
            except Exception as e:
                logger.error(f"Failed to delete VM {vm_id}: {e}")

        self._initialized = False
        logger.info(f"VM pool shutdown complete (stats: {self._stats})")

    def get_pool_status(self) -> Dict[str, Any]:
        """
        Get current pool status for monitoring.

        Returns:
            Dict with pool state, VM info, and statistics
        """
        return {
            "initialized": self._initialized,
            "pool_size": self.pool_size,
            "snapshot_name": self.snapshot_name,
            "vms": {vm_id: vm.to_dict() for vm_id, vm in self._vms.items()},
            "available_count": sum(
                1 for vm in self._vms.values() if vm.state == VMState.AVAILABLE
            ),
            "in_use_count": sum(
                1 for vm in self._vms.values() if vm.state == VMState.IN_USE
            ),
            "failed_count": sum(
                1 for vm in self._vms.values() if vm.state == VMState.FAILED
            ),
            "stats": self._stats.copy(),
        }

    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized"""
        return self._initialized
