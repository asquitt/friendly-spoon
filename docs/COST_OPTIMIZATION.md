# Cost Optimization Guide

This guide explains how to minimize costs while running the LLM Feature Store.

## 💰 Cost Breakdown

### Local Development (Recommended for Testing)
- **Total cost: $0/month**
- All services run locally via Docker Compose
- No cloud infrastructure needed
- Perfect for learning and testing

### Production (1M requests/month)

#### Without Optimization
| Component | Service | Monthly Cost |
|-----------|---------|--------------|
| Compute | EC2 t3.medium 24/7 | $30 |
| Database | RDS PostgreSQL | $100 |
| Analytics | BigQuery (1TB queries) | $50 |
| Storage | S3 Standard (100GB) | $2.30 |
| Embeddings | OpenAI API (1M embeddings) | $100 |
| Cache | ElastiCache Redis | $15 |
| **Total** | | **$297.30** |

#### With Our Optimizations
| Component | Service | Monthly Cost | Savings |
|-----------|---------|--------------|---------|
| Compute | Lambda/OpenFaaS (serverless) | $5 | $25 |
| Database | DynamoDB on-demand | $10 | $90 |
| Analytics | DuckDB (self-hosted) | $0 | $50 |
| Storage | S3 Intelligent-Tiering | $1.50 | $0.80 |
| Embeddings | Local model + cache | $0 | $100 |
| Cache | Redis on EC2 t4g.small | $8 | $7 |
| **Total** | | **$24.50** | **$272.80** |

**Total Savings: 91.8%** 🎉

## 🎯 Cost Optimization Strategies

### 1. Use Local Embedding Models (Biggest Saver!)

**Problem**: OpenAI embeddings cost ~$0.0001 per embedding
- 1M embeddings = $100/month
- 10M embeddings = $1,000/month

**Solution**: Use sentence-transformers locally
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode("Your text here")
```

**Savings**: $100/month → $0/month (100% savings)

**Trade-offs**:
- Slightly slower (50ms vs 200ms)
- Different embedding space (not compatible with OpenAI)
- Need to host the model (~500MB)

**Verdict**: ✅ Worth it! Quality is good enough for most use cases.

### 2. Aggressive Caching

**Problem**: Repeated embeddings/queries waste money

**Solution**: Cache everything with Redis
```python
# Cache embeddings for 24 hours (or longer)
cache.set_embedding(text, embedding, ttl=86400)

# Typical cache hit rate: 95%+
```

**Savings**: 95% reduction in API calls
- Without cache: $100/month
- With 95% hit rate: $5/month
- **Savings: $95/month**

**Best Practices**:
- Cache embeddings for 24 hours minimum
- Cache features for 5 minutes
- Use Redis LRU eviction to automatically remove old entries
- Monitor cache hit rate (aim for >90%)

### 3. Use DuckDB Instead of BigQuery

**Problem**: BigQuery charges per TB queried
- 1TB queried = $5
- Typical analytics workload: 10TB/month = $50

**Solution**: Use DuckDB for analytics
```python
import duckdb

# Free, fast, local
conn = duckdb.connect('features.duckdb')
result = conn.execute("SELECT AVG(cost) FROM interactions").fetchall()
```

**Savings**: $50/month → $0/month

**Trade-offs**:
- DuckDB is single-machine (not distributed)
- Need to manage the database file yourself
- For very large datasets (>100GB), BigQuery might be better

**Verdict**: ✅ Perfect for most use cases. Switch to BigQuery only if you have >100GB of data.

### 4. Serverless Functions (Scale to Zero)

**Problem**: Always-on servers waste money
- EC2 t3.medium 24/7 = $30/month
- 90% of time: idle, but still paying

**Solution**: Use serverless functions
```python
# OpenFaaS function (scales to zero)
def handle(req):
    # Process request
    return response
```

**Savings**: $30/month → $5/month
- Pay only for execution time
- Auto-scales with load
- Zero cost when idle

**Best Practices**:
- Keep functions warm (pre-load models)
- Batch requests when possible
- Use async processing for long-running tasks

### 5. S3 Intelligent-Tiering

**Problem**: S3 Standard charges the same for all data
- Frequently accessed: $0.023/GB/month
- Rarely accessed: Could be cheaper

**Solution**: Use S3 Intelligent-Tiering
```terraform
resource "aws_s3_bucket" "feature_store" {
  bucket = "my-feature-store"
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "feature_store" {
  bucket = aws_s3_bucket.feature_store.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }
}
```

**Savings**: 35% on average
- Hot data: $0.023/GB
- Cool data: $0.0125/GB (45% cheaper)
- Archive: $0.004/GB (83% cheaper)

**Verdict**: ✅ Set and forget. AWS automatically moves data between tiers.

### 6. DynamoDB On-Demand Pricing

**Problem**: Provisioned capacity wastes money
- Provision for peak load
- Pay for capacity even when idle

**Solution**: Use on-demand pricing
```terraform
resource "aws_dynamodb_table" "features" {
  name         = "llm-features"
  billing_mode = "PAY_PER_REQUEST"
  # ...
}
```

**Savings**: 50-80% depending on traffic pattern
- Only pay for actual reads/writes
- Auto-scales with load
- No capacity planning needed

**Best Practices**:
- Use on-demand for unpredictable workloads
- Switch to provisioned if you have consistent traffic (cheaper at scale)

### 7. Batch Processing

**Problem**: Processing one event at a time is inefficient
- More network calls
- Can't leverage batching

**Solution**: Batch events
```python
# Process 100 events at once
batch = []
for event in events:
    batch.append(event)
    if len(batch) >= 100:
        process_batch(batch)
        batch = []
```

**Savings**: 50% reduction in function invocations
- Fewer cold starts
- Better throughput
- Lower per-request cost

### 8. Spot Instances for Batch Jobs

**Problem**: On-demand EC2 is expensive for batch workloads

**Solution**: Use Spot Instances (70-90% cheaper!)
```terraform
resource "aws_spot_instance_request" "batch_worker" {
  instance_type = "t3.medium"
  spot_price    = "0.01"  # 90% cheaper than on-demand
  # ...
}
```

**Savings**: $30/month → $3/month

**Trade-offs**:
- Can be interrupted
- Not suitable for real-time workloads
- Need to handle interruptions gracefully

**Verdict**: ✅ Perfect for batch jobs like feature computation, drift detection

## 📊 Cost Monitoring

### Set Up Cost Alerts

```python
# Track costs in real-time
from src.shared.logger import log_cost_metric

log_cost_metric(
    log,
    operation="embedding",
    model="gpt-4",
    input_tokens=100,
    output_tokens=50,
    cost_usd=0.01,
    latency_ms=1200,
    cache_hit=False
)
```

### View Cost Dashboard

```python
# Get daily cost breakdown
from src.storage.feature_store import FeatureStore

fs = FeatureStore()
summary = fs.get_cost_summary(days=30)

print(f"Total: ${summary['total_cost']:.2f}")
for model, cost in summary['cost_by_model'].items():
    print(f"{model}: ${cost:.2f}")
```

### Set Cost Budgets

```terraform
resource "aws_budgets_budget" "monthly" {
  name         = "llm-feature-store-monthly"
  budget_type  = "COST"
  limit_amount = "50"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 80  # Alert at 80% of budget
    threshold_type      = "PERCENTAGE"
    notification_type   = "ACTUAL"
    subscriber_email_addresses = ["your-email@example.com"]
  }
}
```

## 🎓 Cost Optimization Checklist

- [ ] ✅ Use local embedding models (not OpenAI)
- [ ] ✅ Enable Redis caching (24h TTL for embeddings)
- [ ] ✅ Use DuckDB for analytics (not BigQuery)
- [ ] ✅ Deploy serverless functions (not always-on servers)
- [ ] ✅ Enable S3 Intelligent-Tiering
- [ ] ✅ Use DynamoDB on-demand pricing
- [ ] ✅ Batch process events (100+ at a time)
- [ ] ✅ Monitor cache hit rate (aim for >90%)
- [ ] ✅ Set up cost alerts (AWS Budgets)
- [ ] ✅ Review costs monthly

## 💡 Advanced Optimization

### For High-Volume Workloads (10M+ requests/month)

1. **Use Reserved Instances** (40-60% cheaper than on-demand)
2. **Switch to Provisioned DynamoDB** (cheaper at scale)
3. **Use CloudFront CDN** for read-heavy workloads
4. **Compress data** before storing in S3 (gzip = 70% smaller)
5. **Archive old data** to Glacier (90% cheaper)

### For Low-Volume Workloads (<100K requests/month)

1. **Run everything locally** (zero cloud costs)
2. **Use free tiers** (Lambda, DynamoDB, S3 all have free tiers)
3. **Single EC2 instance** instead of managed services

## 📚 Further Reading

- [AWS Cost Optimization Best Practices](https://aws.amazon.com/pricing/cost-optimization/)
- [Sentence Transformers Documentation](https://www.sbert.net/)
- [DuckDB Performance Guide](https://duckdb.org/docs/guides/performance/overview)

---

**Remember**: The biggest cost savings come from:
1. 🔢 Local embeddings (90%+ savings)
2. 💾 Aggressive caching (90%+ savings)
3. 📊 DuckDB for analytics (100% savings vs BigQuery)

Start with these three and you'll already be saving hundreds of dollars per month!
