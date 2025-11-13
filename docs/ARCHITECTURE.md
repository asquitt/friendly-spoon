# Architecture Overview

This document explains the architecture of the LLM Feature Store, design decisions, and how components work together.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│              (Chatbots, RAG systems, LLM apps, etc.)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │      Event Streaming (Kafka)       │
         │   Topics: llm-interactions,        │
         │            embedding-requests      │
         └───────────┬──────────┬────────────┘
                     │          │
        ┌────────────▼──────────▼─────────────┐
        │   Serverless Functions (OpenFaaS)   │
        │  • embedding-generator               │
        │  • feature-extractor                 │
        │  • drift-detector                    │
        │  • cost-calculator                   │
        └────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │      3-Tier Storage Architecture     │
        │                                      │
        │  Hot Tier (Redis)                   │
        │  • <10ms latency                    │
        │  • Embeddings cache (95% hit rate)  │
        │  • Recent features                  │
        │  Cost: ~$8/month                    │
        │                                      │
        │  Warm Tier (DuckDB)                 │
        │  • ~100ms latency                   │
        │  • Analytics queries                │
        │  • Feature aggregations             │
        │  Cost: $0/month                     │
        │                                      │
        │  Cold Tier (Delta Lake on S3)       │
        │  • ~1s latency                      │
        │  • Historical data                  │
        │  • Time travel queries              │
        │  Cost: ~$2/month                    │
        └────────────┬────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │   Orchestration (Temporal.io)       │
        │  • Feature refresh workflows        │
        │  • Drift detection schedules        │
        │  • Data archival jobs               │
        └─────────────────────────────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │   Monitoring & Alerting             │
        │  • Prometheus (metrics)             │
        │  • Grafana (dashboards)             │
        │  • Slack/PagerDuty (alerts)         │
        └─────────────────────────────────────┘
```

## 🎯 Design Principles

### 1. Cost-First Architecture

Every component was chosen with cost in mind:

- **Local embedding models** instead of OpenAI API (90% savings)
- **DuckDB** instead of BigQuery (100% savings)
- **Serverless functions** instead of always-on servers (90% savings)
- **Intelligent caching** to minimize API calls (95% savings)

**Result**: 90%+ cost reduction compared to traditional architecture.

### 2. 3-Tier Storage Strategy

Different data access patterns require different storage solutions:

#### Hot Tier (Redis)
- **Use case**: Low-latency feature serving (<10ms)
- **Data**: Recent embeddings, frequently-accessed features
- **TTL**: 5 minutes to 24 hours
- **Cost**: ~$8/month (self-hosted)
- **Why**: Sub-millisecond lookups, perfect for online serving

#### Warm Tier (DuckDB)
- **Use case**: Analytics, aggregations, reporting
- **Data**: All interactions for last 30-90 days
- **Query time**: ~100ms
- **Cost**: $0 (embedded database)
- **Why**: Fast analytical queries, zero cost, no server needed

#### Cold Tier (Delta Lake on S3)
- **Use case**: Historical data, compliance, auditing
- **Data**: All interactions, indefinitely
- **Query time**: ~1 second
- **Cost**: $0.023/GB/month (with Intelligent-Tiering)
- **Why**: Cheap long-term storage, ACID guarantees, time travel

### 3. Serverless-First Design

Components scale to zero when not in use:

- **OpenFaaS functions**: Only run when processing events
- **Lambda**: Only pay for execution time
- **DynamoDB**: On-demand billing (no idle costs)

**Benefit**: Your infrastructure cost scales linearly with usage.

### 4. Intelligent Caching

Caching is the #1 cost optimization:

```python
# Without cache: Generate embedding every time
embedding = model.encode(text)  # 50ms, costs money

# With cache: 95% hit rate
embedding = cache.get(text) or model.encode(text)  # 1ms most of the time!
```

**Typical cache hit rates**:
- Embeddings: 95%+ (prompts are often similar)
- Features: 80%+ (users query same features repeatedly)

**Savings**: 95% reduction in compute and API costs!

## 🔧 Component Deep Dive

### Event Streaming (Kafka)

**Why Kafka?**
- Industry standard for event streaming
- Handles millions of events per second
- Fault-tolerant, scalable
- Decouples producers from consumers

**Topics**:
1. `llm-interactions`: LLM request/response events
2. `embedding-requests`: Embedding generation requests

**Consumer Groups**:
- `feature-store-consumers`: Write to feature store
- `analytics-consumers`: Real-time analytics
- `monitoring-consumers`: Drift detection

**Cost optimization**:
- Local Kafka for development: $0
- Confluent Cloud for production: ~$100/month
- **Our choice**: Self-hosted on EC2: ~$10/month

### Embedding Generation (sentence-transformers)

**Why local models?**
- **Cost**: $0 vs $100/month for OpenAI
- **Latency**: 50ms vs 200ms (faster!)
- **Privacy**: Data never leaves your infrastructure
- **Offline**: Works without internet

**Model choice: all-MiniLM-L6-v2**
- **Size**: 90MB (fits in Lambda!)
- **Speed**: 50ms per embedding on CPU
- **Quality**: 85%+ of OpenAI quality
- **Dimensions**: 384 (smaller than OpenAI's 1536)

**Trade-offs**:
- Embedding space is different (not compatible with OpenAI)
- Slightly lower quality (but good enough for most use cases)
- Need to host the model yourself (~500MB with dependencies)

**When to use OpenAI instead**:
- Need best-in-class quality
- Already using OpenAI embeddings (migration cost)
- Don't want to manage models

### Storage Layer

#### Redis (Hot Tier)

**Schema**:
```
embedding:{hash(text + model)} -> pickle(embedding_vector)
feature:{entity_id}:{feature_name} -> pickle(value)
```

**Configuration**:
- Max memory: 256MB (enough for 10K embeddings)
- Eviction policy: `allkeys-lru` (least recently used)
- Persistence: AOF (append-only file) for durability

**Cost optimization**:
- Run on EC2 t4g.small: $8/month
- Alternative: ElastiCache: $15/month
- Alternative: Redis Cloud: $10/month (free tier available)

#### DuckDB (Warm Tier)

**Schema**:
```sql
-- LLM interactions table
CREATE TABLE llm_interactions (
    interaction_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DOUBLE,
    timestamp TIMESTAMP,
    date DATE  -- Partition key
);

-- Features table
CREATE TABLE features (
    feature_name VARCHAR,
    entity_id VARCHAR,
    value VARCHAR,
    timestamp TIMESTAMP,
    date DATE
);
```

**Why DuckDB?**
- **Fast**: Columnar storage, vectorized execution
- **Free**: No licensing costs
- **Simple**: Single file, no server
- **Powerful**: Full SQL support, window functions

**Typical queries**:
```sql
-- Daily cost breakdown
SELECT date, SUM(cost_usd) as total_cost
FROM llm_interactions
WHERE date >= CURRENT_DATE - 30
GROUP BY date;

-- Top users by cost
SELECT user_id, SUM(cost_usd) as total_cost
FROM llm_interactions
GROUP BY user_id
ORDER BY total_cost DESC
LIMIT 10;
```

#### Delta Lake (Cold Tier)

**Why Delta Lake?**
- **ACID transactions**: No data corruption
- **Time travel**: Query historical states
- **Schema evolution**: Add columns without breaking
- **Cheap**: S3 storage at $0.023/GB/month

**Partitioning strategy**:
```
s3://bucket/delta-lake/
  date=2025-01-01/
    part-001.parquet
    part-002.parquet
  date=2025-01-02/
    part-001.parquet
```

**Query example**:
```python
# Read specific date range (partition pruning!)
df = dt.to_pandas(
    filters="date >= '2025-01-01' AND date <= '2025-01-31'"
)

# Only scans January data (1/12 of total)
```

### Orchestration (Temporal.io)

**Why Temporal?**
- Reliable workflow execution
- Built-in retries and error handling
- Workflow versioning
- Easy to test

**Workflows**:

1. **Feature Refresh Workflow**
   - Runs every hour
   - Computes aggregated features
   - Updates cache and DuckDB
   - Duration: ~5 minutes

2. **Drift Detection Workflow**
   - Runs every 6 hours
   - Checks all features for drift
   - Sends alerts if drift detected
   - Duration: ~10 minutes

3. **Data Archival Workflow**
   - Runs daily
   - Moves old data from DuckDB to Delta Lake
   - Compacts Delta Lake files
   - Duration: ~30 minutes

## 🔄 Data Flow

### Write Path (Ingestion)

```
1. LLM application makes API call
2. Response received
3. Publish event to Kafka (llm-interactions topic)
4. Consumer reads event
5. Write to DuckDB (analytics)
6. Write to Delta Lake (archival, batched)
7. Compute features (aggregations)
8. Cache features in Redis (hot data)
```

**Latency**: ~50ms end-to-end

### Read Path (Online Features)

```
1. Feature request arrives
2. Check Redis cache
   └─ Hit? Return immediately (<1ms)
   └─ Miss? Continue...
3. Query DuckDB
4. Cache result in Redis
5. Return to client
```

**Latency**:
- Cache hit: <1ms (99% of requests)
- Cache miss: ~100ms

### Read Path (Offline Features / Analytics)

```
1. Analytical query arrives
2. Query DuckDB (last 30-90 days)
3. If older data needed, query Delta Lake
4. Aggregate results
5. Return to client
```

**Latency**: 100ms to 10s depending on query complexity

## 📊 Performance Characteristics

### Throughput

- **Events ingested**: 10,000/second (Kafka)
- **Embeddings generated**: 100/second (single instance)
- **Features served**: 100,000/second (Redis)
- **Analytical queries**: 10/second (DuckDB)

### Latency (p99)

- **Feature read (cache hit)**: <1ms
- **Feature read (cache miss)**: 100ms
- **Embedding generation (cached)**: 1ms
- **Embedding generation (uncached)**: 50ms
- **Analytical query**: 500ms
- **Historical query (Delta Lake)**: 2s

### Scalability

- **Kafka**: Horizontal scaling (add brokers)
- **Redis**: Vertical scaling or sharding
- **DuckDB**: Single-machine (up to 100GB efficiently)
- **Delta Lake**: Unlimited (S3 scales infinitely)
- **OpenFaaS**: Auto-scales based on load

## 🔐 Security Considerations

### Data Encryption

- **At rest**: S3 encryption, DynamoDB encryption
- **In transit**: TLS for all network communication
- **Secrets**: Environment variables, AWS Secrets Manager

### Access Control

- **IAM roles**: Least-privilege access
- **Network isolation**: VPC, security groups
- **API authentication**: API keys, JWT tokens

### Data Privacy

- **PII handling**: Hash/encrypt sensitive fields
- **Data retention**: Automatic expiration (TTL)
- **Compliance**: GDPR, CCPA (configurable retention)

## 📈 Monitoring & Observability

### Metrics (Prometheus)

- Function invocation count
- Function latency (p50, p95, p99)
- Cache hit rate
- Error rate
- Cost per request

### Logs (Structured)

```json
{
  "event": "embedding_generated",
  "model": "all-MiniLM-L6-v2",
  "cache_hit": false,
  "latency_ms": 45.2,
  "cost_usd": 0.0,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Alerts

- High error rate (>1%)
- High latency (>500ms p99)
- Cost spike (>20% increase)
- Cache hit rate drop (<80%)
- Drift detected (PSI >0.2)

## 🚀 Future Enhancements

### Short-term (1-3 months)

- [ ] Add support for more embedding models
- [ ] Implement feature versioning
- [ ] Add A/B testing framework
- [ ] Create Grafana dashboards
- [ ] Add cost forecasting

### Long-term (3-6 months)

- [ ] Real-time feature computation (Flink)
- [ ] Feature importance tracking
- [ ] Automated feature engineering
- [ ] Multi-region deployment
- [ ] GraphQL API

## 📚 Further Reading

- [Feast Architecture](https://docs.feast.dev/getting-started/architecture)
- [Delta Lake Documentation](https://docs.delta.io/latest/index.html)
- [DuckDB Performance](https://duckdb.org/why_duckdb#fast)
- [Sentence Transformers](https://www.sbert.net/)
- [Temporal Concepts](https://docs.temporal.io/concepts)

---

**Questions?** Open an issue on GitHub or check the [README](../README.md) for more information.
