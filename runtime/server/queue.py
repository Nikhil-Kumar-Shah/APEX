"""Async Request Queue and concurrency control manager."""

import asyncio
import logging
from typing import Any, Dict, Generator, Optional, Tuple

logger = logging.getLogger("runtime.server.queue")


class QueueFullError(Exception):
    """Raised when the request queue has reached its maximum capacity."""
    pass


class RequestQueue:
    """Buffers incoming LLM requests and schedules them sequentially to prevent GPU overload."""

    def __init__(self, max_size: int = 10):
        """Initializes the RequestQueue.

        Args:
            max_size: Maximum number of pending requests allowed in the queue.
        """
        self.max_size = max_size
        self._queue: asyncio.Queue[Tuple[str, Dict[str, Any], asyncio.Queue, asyncio.Event]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.model_manager: Optional[Any] = None

    def start_worker(self, model_manager: Any) -> None:
        """Starts the background queue consumer worker.

        Args:
            model_manager: Reference to the ModelManager instance.
        """
        self.model_manager = model_manager
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("[+] Request Queue background worker started.")

    async def stop_worker(self) -> None:
        """Stops the background queue worker gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("[-] Request Queue background worker stopped.")

    async def enqueue_request(
        self,
        prompt: str,
        generation_params: Dict[str, Any],
    ) -> Tuple[asyncio.Queue[Optional[str]], asyncio.Event]:
        """Enqueues a new request for execution.

        Args:
            prompt: Input text prompt.
            generation_params: Dict of generation hyperparameters.

        Returns:
            Tuple[asyncio.Queue, asyncio.Event]: A queue yielding tokens and a cancellation event.
        """
        if self._queue.qsize() >= self.max_size:
            raise QueueFullError("The server request queue is full. Try again later.")

        token_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        cancel_event = asyncio.Event()

        # Enqueue request payload
        await self._queue.put((prompt, generation_params, token_queue, cancel_event))
        return token_queue, cancel_event

    async def _process_queue(self) -> None:
        """Background loop retrieving and executing requests sequentially."""
        while True:
            try:
                prompt, params, token_queue, cancel_event = await self._queue.get()
                try:
                    # Check cancellation before executing
                    if cancel_event.is_set():
                        await token_queue.put(None)
                        continue

                    # Delegate model inference to thread pool to avoid blocking ASGI loop
                    await self._execute_inference(prompt, params, token_queue, cancel_event)
                except Exception as e:
                    logger.error(f"Error during queued inference: {e}", exc_info=True)
                    # Notify stream client of internal failure
                    await token_queue.put(f"[Error]: {e}")
                    await token_queue.put(None)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue worker encountered unexpected error: {e}")
                await asyncio.sleep(1)

    async def _execute_inference(
        self,
        prompt: str,
        params: Dict[str, Any],
        token_queue: asyncio.Queue[Optional[str]],
        cancel_event: asyncio.Event,
    ) -> None:
        """Handles running the synchronous generator in a separate thread."""
        if not self.model_manager or not self.model_manager.active_engine:
            raise RuntimeError("No model or active engine loaded.")

        engine = self.model_manager.active_engine

        # Synchronous stream generation wrapper
        def generate_sync() -> Generator[str, None, None]:
            return engine.generate_stream(prompt, params)

        # Run generator in separate thread
        try:
            # We fetch generator from thread safely
            gen = await asyncio.to_thread(generate_sync)
            
            def get_next_token(g):
                try:
                    return next(g)
                except StopIteration:
                    return None

            while True:
                # Check for client cancellation
                if cancel_event.is_set():
                    logger.info("Generation cancelled by client.")
                    break
                
                token = await asyncio.to_thread(get_next_token, gen)
                if token is None:
                    break
                await token_queue.put(token)

        finally:
            # Always signal end of stream by putting None
            await token_queue.put(None)

    def get_status(self) -> Dict[str, Any]:
        """Retrieves queue load statistics.

        Returns:
            Dict[str, Any]: Current size and limit.
        """
        return {
            "current_size": self._queue.qsize(),
            "max_size": self.max_size,
        }
