"""Hardware introspection service interface."""

from abc import ABC, abstractmethod
from typing import Any


class HardwareService(ABC):
    """Contract for querying host hardware metrics.

    Future methods:
    - get_gpu()
    - get_cpu()
    - get_ram()
    - get_cuda()
    """

    @abstractmethod
    async def get_gpu(self) -> dict[str, Any]:
        """Return GPU model, memory, and utilization information."""

    @abstractmethod
    async def get_cpu(self) -> dict[str, Any]:
        """Return CPU model and utilization information."""

    @abstractmethod
    async def get_ram(self) -> dict[str, Any]:
        """Return system memory usage information."""

    @abstractmethod
    async def get_cuda(self) -> dict[str, Any]:
        """Return CUDA runtime and driver information."""

    @abstractmethod
    async def get_summary(self) -> dict[str, Any]:
        """Return an aggregated hardware summary for API responses."""
