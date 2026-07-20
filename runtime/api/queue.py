"""Request queue for safe GPU concurrency."""

import asyncio
import logging
from typing import Callable, Any

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState

logger = logging.getLogger("runtime.api.queue")

class RequestQueue:
    """
    GPU-safe request queue. 
    Enforces a strict MAX_CONCURRENT_REQUESTS limit.
    Blocks extra requests until a slot opens up, preventing OOM crashes.
    """
    def __init__(self, config: APIConfig, state: RuntimeState):
        self.config = config
        self.state = state
        # A semaphore limits the number of concurrent executions
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Executes the function when a slot in the queue is available."""
        if not self.config.enable_queue:
            return await func(*args, **kwargs)
            
        self.state.queue_size += 1
        try:
            # Wait for our turn
            async with self.semaphore:
                self.state.queue_size -= 1
                return await func(*args, **kwargs)
        except Exception:
            # If an exception happens while waiting or running, we ensure queue size decrements properly
            if self.semaphore.locked():
                pass # Already decremented inside context
            else:
                self.state.queue_size -= 1
            raise
