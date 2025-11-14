# Glossary - LLM Feature Store Terms

A comprehensive glossary of terms used throughout the learning path.

---

## A

**API (Application Programming Interface)**
- A set of rules and protocols for building software applications
- In this project: Interfaces for interacting with LLM services

**Analytical Storage**
- Database optimized for complex queries and analytics
- Example: DuckDB in this project

---

## C

**Cache**
- Temporary storage for frequently accessed data
- Improves performance by reducing redundant computations
- Example: Redis cache in this project

**Cache Hit**
- When requested data is found in the cache
- Faster than computing/fetching from original source

**Cache Miss**
- When requested data is NOT found in the cache
- Requires computation/fetching from original source

**Cache Hit Rate**
- Percentage of requests served from cache
- Formula: cache_hits / (cache_hits + cache_misses)
- Target: >90% for good performance

**CRUD Operations**
- Create, Read, Update, Delete
- Basic operations for data management

---

## D

**Delta Lake**
- Open-source storage layer that brings ACID transactions to data lakes
- Built on top of Parquet files
- Provides time travel and schema evolution

**Drift Detection**
- Monitoring for changes in data distribution over time
- Critical for ML model performance
- Methods: PSI (Population Stability Index), KS test

**DuckDB**
- Embeddable analytical database (like SQLite for analytics)
- Fast, in-process SQL OLAP database
- Perfect for local analytics

---

## E

**Embedding**
- Dense vector representation of text/data
- Captures semantic meaning
- Example: "cat" and "kitten" have similar embeddings

**Embedding Dimension**
- Size of the embedding vector
- Common sizes: 384, 768, 1536
- Larger = more information, slower computation

**Embedding Model**
- Model that converts text to embeddings
- Examples: sentence-transformers, OpenAI embeddings
- This project uses sentence-transformers (free!)

---

## F

**Feature**
- Input variable used in machine learning models
- Can be raw data or computed values
- Examples: user_age, avg_session_duration, text_embedding

**Feature Store**
- Centralized repository for storing and serving features
- Provides online (real-time) and offline (batch) access
- Ensures consistency between training and inference

**Feature Engineering**
- Process of creating features from raw data
- Critical for ML model performance
- Example: Converting timestamps to day_of_week

---

## I

**Idempotent**
- Operation that produces the same result if called multiple times
- Example: Calling close() multiple times safely

**Index (Database)**
- Data structure that improves query speed
- Trade-off: Faster reads, slower writes
- Example: Index on (user_id, date) column

---

## K

**Kafka**
- Distributed streaming platform
- Used for real-time data pipelines
- In this project: Streaming embeddings and features

**KS Test (Kolmogorov-Smirnov Test)**
- Statistical test for drift detection
- Compares two probability distributions
- Outputs p-value (< 0.05 = significant drift)

---

## L

**Latency**
- Time delay between request and response
- Measured in milliseconds (ms)
- Lower is better!

**LLM (Large Language Model)**
- AI model trained on vast amounts of text
- Examples: GPT-4, Claude, Llama
- Can generate text, answer questions, etc.

---

## M

**Model Provider**
- Company/service providing LLM API
- Examples: OpenAI, Anthropic, Google
- Each has different pricing and capabilities

---

## O

**OLAP (Online Analytical Processing)**
- Database optimized for complex queries
- Good for: Analytics, reporting, data warehousing
- Example: DuckDB

**OLTP (Online Transaction Processing)**
- Database optimized for transactions
- Good for: Create, update, delete operations
- Example: PostgreSQL, MySQL

**OpenFaaS**
- Serverless functions framework for Kubernetes
- Deploy functions easily
- Auto-scaling based on load

---

## P

**P50, P95, P99 (Percentiles)**
- Statistical measures of latency
- P50 (median): 50% of requests faster than this
- P95: 95% of requests faster than this
- P99: 99% of requests faster than this

**Parquet**
- Columnar storage file format
- Efficient for analytics
- Used by Delta Lake

**PSI (Population Stability Index)**
- Metric for detecting drift
- Compares distributions across time periods
- PSI < 0.1: Stable, 0.1-0.25: Moderate drift, >0.25: Significant drift

**Pydantic**
- Python library for data validation
- Uses type hints
- Provides helpful error messages

---

## R

**Redis**
- In-memory key-value store
- Very fast (sub-millisecond latency)
- Used for caching in this project

**Retry Logic**
- Automatic retry of failed operations
- Often with exponential backoff
- Improves reliability

---

## S

**Semantic Search**
- Search based on meaning, not just keywords
- Uses embeddings for similarity
- Example: "car" matches "automobile"

**Sentence-Transformers**
- Python library for embeddings
- Pre-trained models available
- Free to use locally!

**Serverless**
- Cloud computing model
- Pay only for execution time
- Auto-scaling

**Structured Logging**
- Logging with consistent format (usually JSON)
- Easy to parse and query
- Better than unstructured logs

---

## T

**TDD (Test-Driven Development)**
- Write tests first, then implementation
- Red → Green → Refactor cycle
- Ensures code meets requirements

**Throughput**
- Number of operations per unit time
- Example: 500 requests/second
- Higher is better!

**Token**
- Unit of text for LLM processing
- Roughly ~4 characters or ~0.75 words
- Pricing based on tokens

**TTL (Time To Live)**
- How long cached data remains valid
- After TTL expires, data is refreshed
- Measured in seconds

**Type Hints**
- Python annotations for variable types
- Example: `def add(a: int, b: int) -> int:`
- Helps catch errors early

---

## V

**Validation**
- Checking data meets requirements
- Example: Age must be >= 0
- Pydantic does this automatically

**Vector**
- List of numbers
- Embeddings are vectors
- Used for similarity calculations

**Vector Search**
- Finding similar vectors
- Used in semantic search
- Example: Find documents similar to query

---

## W

**Workflow Orchestration**
- Coordinating multiple tasks/steps
- Handles dependencies and retries
- Example: Temporal.io

---

## References

- [Pydantic Docs](https://docs.pydantic.dev/)
- [DuckDB Docs](https://duckdb.org/docs/)
- [Redis Docs](https://redis.io/docs/)
- [Sentence-Transformers Docs](https://www.sbert.net/)
- [Delta Lake Docs](https://docs.delta.io/)
