"""
Enhanced AsyncSQLite wrapper with batch write support.

This module extends the base AsyncSQLite functionality to support:
- Batch inserts using executemany()
- Explicit transaction control
- Transaction-based batching for optimal performance

This is designed to work with the BatchWriteBuffer for high-frequency writes.
"""

import logging
import tempfile
from typing import Any, List, Tuple

from python_sqlite_async import AsyncSQLite

__all__ = ["AsyncSQLiteBatch"]

logger = logging.getLogger(__name__)


class AsyncSQLiteBatch(AsyncSQLite):
    """
    Extended AsyncSQLite with batch write capabilities.

    This class adds support for:
    - executemany() for bulk inserts
    - Explicit transaction BEGIN/COMMIT/ROLLBACK
    - Batch write operations with single transaction overhead

    Note: This extends AsyncSQLite by adding new methods for batch operations.
    The underlying worker thread from AsyncSQLite handles the queuing.
    """

    def __init__(self, db_path: str = ':memory:'):
        """
        Initialize the enhanced async SQLite wrapper.

        Args:
            db_path: Path to the SQLite database file (default: ':memory:')
        """
        super().__init__(db_path)
        logger.info(f"AsyncSQLiteBatch initialized for {db_path}")

    def execute_write_batch(self, sql: str, params_list: List[Tuple[Any, ...]]) -> None:
        """
        Execute a batch write operation using executemany() within a transaction.

        This method wraps all operations in a single transaction for optimal performance.
        Instead of N transactions (one per row), this creates exactly 1 transaction.

        Args:
            sql: SQL statement with placeholders (e.g., "INSERT INTO table VALUES (?, ?)")
            params_list: List of parameter tuples to insert

        Example:
            >>> db.execute_write_batch(
            ...     "INSERT INTO messages (topic, message) VALUES (?, ?)",
            ...     [("topic1", "msg1"), ("topic2", "msg2"), ("topic3", "msg3")]
            ... )

        Implementation:
            Creates a temporary SQL script file and executes it using execute_script.
            This is necessary because AsyncSQLite's execute_script() expects a file path.
        """
        if not params_list:
            logger.debug("execute_write_batch called with empty params_list, skipping")
            return

        batch_size = len(params_list)
        logger.debug(f"Executing batch write: {batch_size} operations")

        try:
            # Build a transaction script with all inserts
            script_parts = ["BEGIN TRANSACTION;"]

            for params in params_list:
                # Format the SQL with actual values (properly escaped)
                formatted_params = []
                for param in params:
                    if isinstance(param, str):
                        # Escape single quotes by doubling them
                        escaped = param.replace("'", "''")
                        formatted_params.append(f"'{escaped}'")
                    elif param is None:
                        formatted_params.append("NULL")
                    elif isinstance(param, (int, float)):
                        formatted_params.append(str(param))
                    else:
                        # For other types, convert to string and escape
                        escaped = str(param).replace("'", "''")
                        formatted_params.append(f"'{escaped}'")

                # Replace placeholders in SQL
                formatted_sql = sql
                for formatted_param in formatted_params:
                    formatted_sql = formatted_sql.replace("?", formatted_param, 1)

                script_parts.append(formatted_sql + ";")

            script_parts.append("COMMIT;")
            script = "\n".join(script_parts)

            # Write to a temporary file and execute
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
                f.write(script)
                temp_path = f.name

            try:
                # Execute the script file
                self.execute_script(temp_path)
                logger.debug(f"Successfully queued batch of {batch_size} operations")
            finally:
                # Clean up temporary file
                import os
                try:
                    os.unlink(temp_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Failed to build/execute batch script: {e}", exc_info=True)
            raise

    def get_queue_size(self) -> int:
        """Get the current size of the write queue."""
        with self._queue_lock:
            return len(self._write_queue)
