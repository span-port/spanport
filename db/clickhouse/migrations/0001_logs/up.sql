CREATE TABLE logs
(
    org_id UUID,
    project_id UUID,
    log_id UUID,
    ts DateTime64(9, 'UTC'),
    observed_ts DateTime64(9, 'UTC'),
    service LowCardinality(String),
    level LowCardinality(String),
    severity_number UInt8,
    message String CODEC(ZSTD(3)),
    trace_id String,
    span_id String,
    attributes Map(LowCardinality(String), String) CODEC(ZSTD(3)),
    resource_attributes Map(LowCardinality(String), String) CODEC(ZSTD(3)),
    INDEX idx_message message TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ts)
ORDER BY (org_id, project_id, service, level, ts, log_id)
TTL toDateTime(ts) + INTERVAL 7 DAY
SETTINGS ttl_only_drop_parts = 1
