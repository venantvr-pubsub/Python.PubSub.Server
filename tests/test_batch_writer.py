"""
Tests for the batch writer functionality.
"""

import time
from python_pubsub_server.async_sqlite_batch import AsyncSQLiteBatch
from python_pubsub_server.batch_writer import BatchWriteBuffer


def test_batch_writer_basic():
    """Test basic batch writer functionality."""
    # Create in-memory database
    db = AsyncSQLiteBatch(":memory:")
    db.start()

    # Wait for DB to be ready
    assert db.wait_for_ready(timeout=5), "Database failed to initialize"

    # Create test tables (using the same schema as the actual app)
    db.execute_write("""
        CREATE TABLE messages (
            topic TEXT,
            message_id TEXT,
            message TEXT,
            producer TEXT,
            timestamp REAL
        )
    """)
    db.execute_write("""
        CREATE TABLE consumptions (
            consumer TEXT,
            topic TEXT,
            message_id TEXT,
            message TEXT,
            timestamp REAL
        )
    """)
    db.execute_write("""
        CREATE TABLE subscriptions (
            sid TEXT,
            consumer TEXT,
            topic TEXT,
            connected_at REAL,
            PRIMARY KEY (sid, topic)
        )
    """)
    db.sync(timeout=5)

    # Create batch writer
    batch_writer = BatchWriteBuffer(
        executor=db.execute_write_batch,
        batch_size=10,
        flush_interval_ms=100,
        max_buffer_size=1000
    )

    batch_writer.start()

    try:
        # Add some messages
        for i in range(25):
            batch_writer.add_message(
                topic=f"topic_{i % 3}",
                message_id=f"msg_{i}",
                message=f"Test message {i}",
                producer="test_producer",
                timestamp=time.time()
            )

        # Wait for flush
        time.sleep(0.5)

        # Verify data was written
        rows = db.execute_read("SELECT COUNT(*) FROM messages")
        count = rows[0][0]

        assert count == 25, f"Expected 25 messages, got {count}"

        # Check metrics
        metrics = batch_writer.get_metrics()
        assert metrics["total_writes"] == 25, f"Expected 25 total writes, got {metrics['total_writes']}"
        assert metrics["total_flushes"] > 0, "Expected at least one flush"
        assert metrics["total_batched_items"] == 25, f"Expected 25 batched items, got {metrics['total_batched_items']}"

        print(f"✓ Batch writer test passed!")
        print(f"  - Total writes: {metrics['total_writes']}")
        print(f"  - Total flushes: {metrics['total_flushes']}")
        print(f"  - Average batch size: {metrics['avg_batch_size']}")
        print(f"  - Flush by size: {metrics['flush_by_size']}")
        print(f"  - Flush by time: {metrics['flush_by_time']}")

    finally:
        batch_writer.stop()
        db.stop()


def test_batch_writer_large_volume():
    """Test batch writer with high volume."""
    db = AsyncSQLiteBatch(":memory:")
    db.start()

    assert db.wait_for_ready(timeout=5), "Database failed to initialize"

    # Drop table if exists (in case previous test left it)
    db.execute_write("DROP TABLE IF EXISTS messages")
    db.sync(timeout=1)

    db.execute_write("""
        CREATE TABLE messages (
            topic TEXT,
            message_id TEXT,
            message TEXT,
            producer TEXT,
            timestamp REAL
        )
    """)
    db.sync(timeout=5)

    batch_writer = BatchWriteBuffer(
        executor=db.execute_write_batch,
        batch_size=100,
        flush_interval_ms=50,
        max_buffer_size=10000
    )

    batch_writer.start()

    try:
        # Simulate high-frequency writes
        num_messages = 1000
        start_time = time.time()

        for i in range(num_messages):
            batch_writer.add_message(
                topic=f"topic_{i % 10}",
                message_id=f"msg_{i}",
                message=f"High frequency message {i}",
                producer="hf_producer",
                timestamp=time.time()
            )

        # Wait for all flushes
        time.sleep(1.0)

        elapsed = time.time() - start_time

        # Verify all messages written
        rows = db.execute_read("SELECT COUNT(*) FROM messages")
        count = rows[0][0]

        assert count == num_messages, f"Expected {num_messages} messages, got {count}"

        metrics = batch_writer.get_metrics()
        throughput = num_messages / elapsed

        print(f"✓ High volume test passed!")
        print(f"  - Messages: {num_messages}")
        print(f"  - Time: {elapsed:.2f}s")
        print(f"  - Throughput: {throughput:.0f} msg/s")
        print(f"  - Total flushes: {metrics['total_flushes']}")
        print(f"  - Average batch size: {metrics['avg_batch_size']:.1f}")

        # With batch_size=100, we expect about 10 flushes for 1000 messages
        expected_flushes = num_messages / 100
        assert metrics['total_flushes'] <= expected_flushes + 5, \
            f"Too many flushes: {metrics['total_flushes']}, expected ~{expected_flushes}"

    finally:
        batch_writer.stop()
        db.stop()


def test_batch_writer_metrics():
    """Test batch writer metrics collection."""
    db = AsyncSQLiteBatch(":memory:")
    db.start()

    assert db.wait_for_ready(timeout=5), "Database failed to initialize"

    db.execute_write("""
        CREATE TABLE messages (
            topic TEXT,
            message_id TEXT,
            message TEXT,
            producer TEXT,
            timestamp REAL
        )
    """)
    db.sync(timeout=5)

    batch_writer = BatchWriteBuffer(
        executor=db.execute_write_batch,
        batch_size=5,
        flush_interval_ms=50,
        max_buffer_size=100
    )

    batch_writer.start()

    try:
        # Add exactly batch_size messages to trigger size flush
        for i in range(5):
            batch_writer.add_message(
                topic="test",
                message_id=f"msg_{i}",
                message=f"Message {i}",
                producer="test",
                timestamp=time.time()
            )

        time.sleep(0.2)

        metrics = batch_writer.get_metrics()

        # Should have at least one flush by size
        assert metrics["flush_by_size"] > 0, "Expected at least one size-based flush"

        # Add more messages and wait for time-based flush
        for i in range(5, 7):
            batch_writer.add_message(
                topic="test",
                message_id=f"msg_{i}",
                message=f"Message {i}",
                producer="test",
                timestamp=time.time()
            )

        time.sleep(0.3)

        metrics = batch_writer.get_metrics()

        print(f"✓ Metrics test passed!")
        print(f"  - Flush by size: {metrics['flush_by_size']}")
        print(f"  - Flush by time: {metrics['flush_by_time']}")
        print(f"  - Min batch size: {metrics['min_batch_size']}")
        print(f"  - Max batch size: {metrics['max_batch_size']}")

    finally:
        batch_writer.stop()
        db.stop()


if __name__ == "__main__":
    test_batch_writer_basic()
    test_batch_writer_large_volume()
    test_batch_writer_metrics()
    print("\n✅ All batch writer tests passed!")
