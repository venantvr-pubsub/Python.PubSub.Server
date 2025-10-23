"""
Batch Write Buffer for High-Performance Sequential Database Writes

This module implements an intelligent write buffering system optimized for
high-frequency trading and event-driven architectures. It reduces database
transaction overhead by batching multiple writes into single transactions.

Key Features:
- Time-based flush (latency control)
- Size-based flush (throughput optimization)
- Separate buffers per operation type
- Thread-safe operation
- Comprehensive metrics
"""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["BatchWriteBuffer", "BatchMetrics", "OperationType", "WriteOperation"]

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of database operations that can be batched."""
    MESSAGE = "messages"
    CONSUMPTION = "consumptions"
    SUBSCRIPTION = "subscriptions"
    DELETION = "deletions"


@dataclass
class BatchMetrics:
    """Metrics for monitoring batch write performance."""
    total_flushes: int = 0
    total_writes: int = 0
    total_batched_items: int = 0
    flush_by_size: int = 0
    flush_by_time: int = 0
    flush_by_shutdown: int = 0
    avg_batch_size: float = 0.0
    last_flush_time: float = 0.0
    max_batch_size: int = 0
    min_batch_size: int = 0

    def record_flush(self, batch_size: int, reason: str) -> None:
        """Record a flush operation."""
        self.total_flushes += 1
        self.total_batched_items += batch_size
        self.last_flush_time = time.time()

        if reason == "size":
            self.flush_by_size += 1
        elif reason == "time":
            self.flush_by_time += 1
        elif reason == "shutdown":
            self.flush_by_shutdown += 1

        # Update batch size statistics
        if self.max_batch_size == 0 or batch_size > self.max_batch_size:
            self.max_batch_size = batch_size
        if self.min_batch_size == 0 or batch_size < self.min_batch_size:
            self.min_batch_size = batch_size

        # Calculate rolling average
        self.avg_batch_size = self.total_batched_items / self.total_flushes if self.total_flushes > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_flushes": self.total_flushes,
            "total_writes": self.total_writes,
            "total_batched_items": self.total_batched_items,
            "flush_by_size": self.flush_by_size,
            "flush_by_time": self.flush_by_time,
            "flush_by_shutdown": self.flush_by_shutdown,
            "avg_batch_size": round(self.avg_batch_size, 2),
            "max_batch_size": self.max_batch_size,
            "min_batch_size": self.min_batch_size,
            "last_flush_time": self.last_flush_time,
        }


@dataclass
class WriteOperation:
    """Represents a single write operation to be batched."""
    operation_type: OperationType
    params: Tuple[Any, ...]
    timestamp: float = field(default_factory=time.time)


class BatchWriteBuffer:
    """
    Intelligent write buffer that batches database operations for optimal performance.

    This class accumulates write operations in memory and flushes them to the database
    in batches, either when:
    1. The batch reaches a configured size (throughput optimization)
    2. A timeout expires (latency control)
    3. The buffer is explicitly flushed or shut down

    Optimized for high-frequency event-driven systems where write throughput
    is critical and bounded latency is acceptable.
    """

    def __init__(
        self,
        executor: Callable[[str, List[Tuple[Any, ...]]], None],
        batch_size: int = 100,
        flush_interval_ms: int = 50,
        max_buffer_size: int = 10000
    ):
        """
        Initialize the batch write buffer.

        Args:
            executor: Function to execute batched writes. Signature: (sql, params_list) -> None
            batch_size: Number of operations to accumulate before auto-flush
            flush_interval_ms: Maximum milliseconds to wait before auto-flush
            max_buffer_size: Maximum buffer size before blocking/dropping writes
        """
        self.executor = executor
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000.0  # Convert to seconds
        self.max_buffer_size = max_buffer_size

        # Separate buffers for each operation type
        self.buffers: Dict[OperationType, deque] = defaultdict(deque)
        self.buffer_locks: Dict[OperationType, threading.Lock] = defaultdict(threading.Lock)

        # Flush control
        self.last_flush_time: Dict[OperationType, float] = defaultdict(lambda: time.time())
        self.flush_thread: Optional[threading.Thread] = None
        self.running = False

        # Metrics
        self.metrics = BatchMetrics()
        self.metrics_lock = threading.Lock()

        logger.info(f"BatchWriteBuffer initialized: batch_size={batch_size}, flush_interval={flush_interval_ms}ms, max_buffer={max_buffer_size}")

    def start(self) -> None:
        """Start the background flush thread."""
        if self.running:
            logger.warning("BatchWriteBuffer is already running")
            return

        self.running = True
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True, name="BatchFlushThread")
        self.flush_thread.start()
        logger.info("BatchWriteBuffer flush thread started")

    def stop(self) -> None:
        """Stop the background flush thread and flush all pending writes."""
        if not self.running:
            logger.warning("BatchWriteBuffer is not running")
            return

        logger.info("Stopping BatchWriteBuffer and flushing pending writes...")
        self.running = False

        if self.flush_thread:
            self.flush_thread.join(timeout=5)

        # Final flush of all buffers
        for op_type in OperationType:
            self._flush_buffer(op_type, reason="shutdown")

        logger.info("BatchWriteBuffer stopped")

    def add_message(self, topic: str, message_id: str, message: Any, producer: str, timestamp: float) -> None:
        """Add a message write operation to the buffer."""
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (topic, message_id, message_json, producer, timestamp)
        self._add_operation(OperationType.MESSAGE, params)

    def add_consumption(self, consumer: str, topic: str, message_id: str, message: Any, timestamp: float) -> None:
        """Add a consumption write operation to the buffer."""
        message_json = json.dumps(message) if not isinstance(message, str) else message
        params = (consumer, topic, message_id, message_json, timestamp)
        self._add_operation(OperationType.CONSUMPTION, params)

    def add_subscription(self, sid: str, consumer: str, topic: str, connected_at: float) -> None:
        """Add a subscription write operation to the buffer."""
        params = (sid, consumer, topic, connected_at)
        self._add_operation(OperationType.SUBSCRIPTION, params)

    def _add_operation(self, op_type: OperationType, params: Tuple[Any, ...]) -> None:
        """Add an operation to the appropriate buffer."""
        with self.buffer_locks[op_type]:
            buffer = self.buffers[op_type]

            # Check buffer size limit
            if len(buffer) >= self.max_buffer_size:
                logger.warning(f"Buffer for {op_type.value} is full ({self.max_buffer_size}), forcing flush")
                self._flush_buffer(op_type, reason="size")

            buffer.append(params)

            with self.metrics_lock:
                self.metrics.total_writes += 1

            # Check if we should flush due to batch size
            if len(buffer) >= self.batch_size:
                self._flush_buffer(op_type, reason="size")

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes buffers based on time."""
        logger.info("Batch flush loop started")

        while self.running:
            try:
                time.sleep(self.flush_interval)

                if not self.running:
                    break

                # Check each buffer for timeout-based flush
                current_time = time.time()
                for op_type in OperationType:
                    with self.buffer_locks[op_type]:
                        buffer = self.buffers[op_type]
                        if len(buffer) > 0:
                            time_since_last_flush = current_time - self.last_flush_time[op_type]
                            if time_since_last_flush >= self.flush_interval:
                                self._flush_buffer(op_type, reason="time")

            except Exception as e:
                logger.error(f"Error in batch flush loop: {e}", exc_info=True)

        logger.info("Batch flush loop stopped")

    def _flush_buffer(self, op_type: OperationType, reason: str) -> None:
        """
        Flush a specific buffer to the database.

        This method must be called with the buffer lock already acquired.
        """
        buffer = self.buffers[op_type]

        if len(buffer) == 0:
            return

        # Extract all operations from buffer
        operations = list(buffer)
        buffer.clear()

        batch_size = len(operations)

        # Update last flush time
        self.last_flush_time[op_type] = time.time()

        # Execute the batch
        try:
            sql = self._get_sql_for_operation(op_type)
            self.executor(sql, operations)

            with self.metrics_lock:
                self.metrics.record_flush(batch_size, reason)

            logger.debug(f"Flushed {batch_size} {op_type.value} operations (reason: {reason})")

        except Exception as e:
            logger.error(f"Failed to flush {batch_size} {op_type.value} operations: {e}", exc_info=True)
            # TODO: Consider re-queueing failed operations or implementing retry logic

    def _get_sql_for_operation(self, op_type: OperationType) -> str:
        """Get the SQL statement for a given operation type."""
        if op_type == OperationType.MESSAGE:
            return "INSERT INTO messages (topic, message_id, message, producer, timestamp) VALUES (?, ?, ?, ?, ?)"
        elif op_type == OperationType.CONSUMPTION:
            return "INSERT INTO consumptions (consumer, topic, message_id, message, timestamp) VALUES (?, ?, ?, ?, ?)"
        elif op_type == OperationType.SUBSCRIPTION:
            return "INSERT OR REPLACE INTO subscriptions (sid, consumer, topic, connected_at) VALUES (?, ?, ?, ?)"
        else:
            raise ValueError(f"Unknown operation type: {op_type}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current batch write metrics."""
        with self.metrics_lock:
            return self.metrics.to_dict()

    def get_buffer_sizes(self) -> Dict[str, int]:
        """Get current sizes of all buffers."""
        sizes = {}
        for op_type in OperationType:
            with self.buffer_locks[op_type]:
                sizes[op_type.value] = len(self.buffers[op_type])
        return sizes

    def force_flush_all(self) -> None:
        """Force immediate flush of all buffers."""
        logger.info("Force flushing all buffers")
        for op_type in OperationType:
            with self.buffer_locks[op_type]:
                self._flush_buffer(op_type, reason="manual")
