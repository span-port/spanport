CREATE TABLE spans
(
    org_id UUID,
    project_id UUID,
    trace_id String,
    span_id String,
    parent_span_id String,
    service LowCardinality(String),
    name String,
    kind LowCardinality(String),
    category LowCardinality(String),
    start_ts DateTime64(9, 'UTC'),
    end_ts DateTime64(9, 'UTC'),
    duration_ns UInt64,
    status_code LowCardinality(String),
    status_message String,
    http_method LowCardinality(String),
    http_route String,
    http_status UInt16,
    attributes Map(LowCardinality(String), String) CODEC(ZSTD(3)),
    resource_attributes Map(LowCardinality(String), String) CODEC(ZSTD(3)),
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_http_route http_route TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(start_ts)
ORDER BY (org_id, project_id, service, category, start_ts)
TTL toDateTime(start_ts) + INTERVAL 30 DAY
SETTINGS ttl_only_drop_parts = 1
