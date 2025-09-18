-- Create new messages table with new columns
DROP TABLE IF EXISTS messages;

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    message_id TEXT,
    message TEXT,
    producer TEXT,
    timestamp REAL
);

-- Create new consumptions table with message_id
DROP TABLE IF EXISTS consumptions;

CREATE TABLE consumptions (
    consumer TEXT,
    topic TEXT,
    message_id TEXT,
    message TEXT,
    timestamp REAL
);

-- Subscriptions table remains unchanged
CREATE TABLE IF NOT EXISTS subscriptions (
    sid TEXT,
    consumer TEXT,
    topic TEXT,
    connected_at REAL,
    PRIMARY KEY (sid, topic)
);

-- Adding indexes to improve query performance on messages table
CREATE INDEX idx_messages_topic ON messages (topic);
CREATE INDEX idx_messages_message_id ON messages (message_id);
CREATE INDEX idx_messages_producer ON messages (producer);
CREATE INDEX idx_messages_timestamp ON messages (timestamp);

-- Adding indexes to improve query performance on consumptions table
CREATE INDEX idx_consumptions_topic ON consumptions (topic);
CREATE INDEX idx_consumptions_consumer ON consumptions (consumer);
CREATE INDEX idx_consumptions_message_id ON consumptions (message_id);
CREATE INDEX idx_consumptions_timestamp ON consumptions (timestamp);

-- Adding indexes to improve query performance on subscriptions table
CREATE INDEX idx_subscriptions_consumer ON subscriptions (consumer);
CREATE INDEX idx_subscriptions_topic ON subscriptions (topic);
CREATE INDEX idx_subscriptions_connected_at ON subscriptions (connected_at);
