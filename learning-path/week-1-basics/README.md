# Week 1: Foundations & Data Models 🎯

**Time**: 8-10 hours | **Difficulty**: ⭐⭐☆☆☆

Welcome to Week 1! This week you'll build the foundation of your LLM Feature Store by learning data modeling with Pydantic, configuration management, structured logging, and testing fundamentals.

---

## 📚 Learning Objectives

By the end of this week, you will be able to:

✅ Create robust data models with Pydantic V2
✅ Implement validation and computed properties
✅ Set up structured logging with structlog
✅ Manage configuration with environment variables
✅ Write unit tests with pytest
✅ Understand type hints and data validation

---

## 📖 Topics Covered

### Day 1-2: Pydantic Data Models (3-4 hours)
- Pydantic V2 basics
- Field validation
- Computed properties
- Model serialization

### Day 3-4: Configuration & Logging (2-3 hours)
- Environment-based configuration
- Pydantic Settings
- Structured logging with structlog
- Log levels and formatting

### Day 5-6: Testing Fundamentals (2-3 hours)
- pytest basics
- Test fixtures
- Parametrized tests
- Coverage reporting

### Day 7: Mini-Project (2-3 hours)
- Build a complete data pipeline
- Integrate all concepts
- Add comprehensive tests

---

## 🎯 What You'll Build

### Core Components

1. **LLM Interaction Model** - Track LLM API calls
2. **Feature Model** - Store computed features
3. **Config System** - Environment-based settings
4. **Logger** - Structured logging
5. **Test Suite** - Comprehensive tests

### End Result

A production-ready data modeling layer that:
- ✅ Validates all inputs automatically
- ✅ Provides helpful error messages
- ✅ Logs structured data
- ✅ Loads configuration from environment
- ✅ Has 90%+ test coverage

---

## 🚀 Getting Started

### Step 1: Review Current Implementation

First, let's look at the production code to understand what we're building:

```bash
# Review the actual models
cat ../../src/shared/models.py

# Review the config system
cat ../../src/shared/config.py

# Review the logger
cat ../../src/shared/logger.py

# Review existing tests
cat ../../tests/test_models.py
```

### Step 2: Start with Starter Code

```bash
cd starter/
ls -la
# You'll see:
# - models.py (with TODO comments)
# - config.py (with TODO comments)
# - logger.py (with TODO comments)
```

### Step 3: Run Tests (They'll Fail Initially)

```bash
# Run tests to see what needs to be implemented
pytest ../tests/ -v

# You should see many failures - that's expected!
# Your goal is to make them all pass
```

---

## 📝 Tutorial

### Part 1: Understanding Pydantic V2

#### What is Pydantic?

Pydantic is a data validation library that uses Python type hints. It:
- Validates data automatically
- Provides helpful error messages
- Converts data types
- Generates JSON schemas

#### Key Concepts

**1. Basic Model**:
```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

# Usage
user = User(name="Alice", age=30)
print(user.name)  # "Alice"

# Validation happens automatically
user = User(name="Bob", age="25")  # age converted to int!
user = User(name="Eve", age="invalid")  # Raises ValidationError!
```

**2. Field Validation**:
```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)  # ge = greater/equal, le = less/equal
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
```

**3. Field Validators (Pydantic V2)**:
```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
```

**4. Computed Fields**:
```python
from pydantic import BaseModel, computed_field

class Rectangle(BaseModel):
    width: float
    height: float

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

rect = Rectangle(width=10, height=5)
print(rect.area)  # 50.0
```

#### Exercise 1.1: Your First Model (15 minutes)

Create a `Book` model with validation:

```python
# TODO: Implement this in starter/models.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional

class Book(BaseModel):
    """Model representing a book."""

    # TODO: Add fields
    # - title: str (required, 1-500 chars)
    # - author: str (required, 1-200 chars)
    # - pages: int (required, must be > 0)
    # - isbn: Optional[str] (optional, 10 or 13 digits)
    # - price: float (required, must be >= 0)

    # TODO: Add validator to ensure title is not just whitespace

    # TODO: Add computed field for price_with_tax (price * 1.08)
```

**Test it**:
```python
# This should work
book = Book(title="Python Crash Course", author="Eric Matthes",
            pages=544, price=39.99)

# This should fail (pages <= 0)
book = Book(title="Bad Book", author="Someone", pages=0, price=10)
```

---

### Part 2: LLM Interaction Model

Now let's build the real model for tracking LLM interactions:

#### Understanding the Requirements

We need to track:
- **Identifiers**: interaction_id, user_id
- **Model Info**: model name, provider (OpenAI, Anthropic, etc.)
- **Content**: prompt, response
- **Metrics**: tokens (input/output/total), latency, cost
- **Metadata**: timestamp, optional metadata JSON

#### Model Design

```python
from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, date
from enum import Enum

class ModelProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    META = "meta"
    COHERE = "cohere"
    OTHER = "other"

class LLMInteraction(BaseModel):
    """
    Model for tracking LLM API interactions.

    This model captures everything about an LLM API call:
    - What was asked (prompt)
    - What was returned (response)
    - How much it cost (tokens, $$$)
    - How long it took (latency)
    """

    # Identifiers
    interaction_id: str = Field(..., description="Unique ID for this interaction")
    user_id: str = Field(..., description="ID of the user making the request")

    # Model information
    model: str = Field(..., description="Model name (e.g., 'gpt-4', 'claude-2')")
    provider: ModelProvider = Field(..., description="LLM provider")

    # Content
    prompt: str = Field(..., description="User prompt/input")
    response: str = Field(..., description="LLM response/output")

    # Metrics
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens")
    latency_ms: float = Field(..., ge=0, description="Response time in milliseconds")
    cost_usd: float = Field(..., ge=0, description="Cost in USD")

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now, description="When this happened")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    # Computed fields
    @computed_field
    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens

    @computed_field
    @property
    def date(self) -> date:
        """Date portion of timestamp (for partitioning)."""
        return self.timestamp.date()

    # Validators
    @field_validator('prompt')
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        """Ensure prompt is not empty."""
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v

    @field_validator('response')
    @classmethod
    def response_not_empty(cls, v: str) -> str:
        """Ensure response is not empty."""
        if not v or not v.strip():
            raise ValueError("Response cannot be empty")
        return v

    # Pydantic config
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "interaction_id": "int_abc123",
                "user_id": "user_xyz789",
                "model": "gpt-4",
                "provider": "openai",
                "prompt": "What is the capital of France?",
                "response": "The capital of France is Paris.",
                "input_tokens": 10,
                "output_tokens": 8,
                "latency_ms": 523.5,
                "cost_usd": 0.0012
            }
        }
    )
```

#### Exercise 1.2: Implement LLMInteraction (30 minutes)

In `starter/models.py`, implement the `LLMInteraction` model:

1. Add all required fields with proper types and validation
2. Implement the two computed properties
3. Implement the two validators
4. Add a model_config with an example

**Test it**:
```bash
pytest ../tests/test_models.py::test_llm_interaction_valid -v
pytest ../tests/test_models.py::test_llm_interaction_computed_fields -v
```

---

### Part 3: Configuration Management

#### Why Configuration Management Matters

Hard-coded values are bad:
```python
# ❌ BAD - Hard-coded
redis_host = "localhost"
redis_port = 6379
db_path = "/tmp/mydb.duckdb"
```

Environment-based config is good:
```python
# ✅ GOOD - From environment
import os
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
db_path = os.getenv("DUCKDB_PATH", ":memory:")
```

#### Using Pydantic Settings

Pydantic provides `BaseSettings` for configuration:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # DuckDB
    duckdb_path: str = ":memory:"

    # Logging
    log_level: str = "INFO"

    # Model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

# Usage
settings = Settings()
print(settings.redis_host)  # Loaded from REDIS_HOST env var or default
```

#### Exercise 1.3: Build Config System (20 minutes)

In `starter/config.py`, implement configuration management:

1. Create settings for Redis, DuckDB, S3, Kafka, Embeddings
2. Add validation for required fields
3. Support `.env` file loading

**Test it**:
```bash
pytest ../tests/test_config.py -v
```

---

### Part 4: Structured Logging

#### Why Structured Logging?

Traditional logging:
```python
# ❌ Hard to parse
logging.info(f"User {user_id} created order {order_id} for ${total}")
```

Structured logging:
```python
# ✅ Easy to parse and query
log.info("order_created", user_id=user_id, order_id=order_id, total=total)

# Output (JSON):
# {"event": "order_created", "user_id": "123", "order_id": "456", "total": 99.99, "timestamp": "2025-11-13T12:00:00Z"}
```

#### Using structlog

```python
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

# Create logger
log = structlog.get_logger()

# Use it
log.info("user_logged_in", user_id="123", ip="192.168.1.1")
log.error("payment_failed", user_id="456", amount=99.99, reason="insufficient_funds")
```

#### Exercise 1.4: Setup Logging (15 minutes)

In `starter/logger.py`, configure structlog:

1. Setup console and file logging
2. Configure JSON formatting
3. Add timestamp and log level

**Test it**:
```bash
python starter/logger.py  # Should output structured logs
```

---

### Part 5: Testing Fundamentals

#### pytest Basics

**Simple Test**:
```python
def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```

**Test with pytest**:
```python
import pytest

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def test_divide():
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3

def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)
```

**Fixtures** (Setup/Teardown):
```python
import pytest

@pytest.fixture
def sample_user():
    """Provide a sample user for tests."""
    return User(name="Alice", age=30, email="alice@example.com")

def test_user_name(sample_user):
    assert sample_user.name == "Alice"

def test_user_age(sample_user):
    assert sample_user.age == 30
```

**Parametrized Tests** (Test Multiple Cases):
```python
import pytest

@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (0, 0, 0),
    (-1, 1, 0),
    (100, 200, 300)
])
def test_add_parametrized(a, b, expected):
    assert add(a, b) == expected
```

#### Exercise 1.5: Write Tests (30 minutes)

In `starter/test_my_models.py`, write tests for your models:

1. Test valid model creation
2. Test validation errors
3. Test computed fields
4. Test edge cases

**Run tests**:
```bash
pytest starter/test_my_models.py -v --cov=starter
```

---

## 🎯 Mini-Project: Complete Data Pipeline

Now let's put it all together! Build a complete data pipeline that:

1. Loads configuration from environment
2. Creates LLM interaction records
3. Validates all data
4. Logs structured events
5. Handles errors gracefully

### Requirements

Create `starter/pipeline.py` that:

```python
"""
Mini-Project: LLM Interaction Pipeline

This script demonstrates a complete data pipeline:
1. Load configuration
2. Create and validate LLM interactions
3. Log structured events
4. Handle errors

Usage:
    python pipeline.py
"""

from typing import List
import structlog
from models import LLMInteraction, ModelProvider
from config import Settings
from logger import setup_logging

# TODO: Implement these functions

def create_sample_interactions() -> List[LLMInteraction]:
    """Create sample LLM interactions for testing."""
    # TODO: Create 5-10 sample interactions
    # Mix different models, providers, and metrics
    pass

def validate_interactions(interactions: List[LLMInteraction]) -> tuple:
    """
    Validate a list of interactions.

    Returns:
        tuple: (valid_count, invalid_count, errors)
    """
    # TODO: Validate each interaction
    # Count valid/invalid
    # Collect error messages
    pass

def process_interactions(interactions: List[LLMInteraction]) -> dict:
    """
    Process interactions and compute summary stats.

    Returns:
        dict: Summary statistics
    """
    # TODO: Compute:
    # - Total interactions
    # - Total tokens
    # - Total cost
    # - Average latency
    # - Interactions by provider
    pass

def main():
    """Main pipeline execution."""
    # TODO: Implement main pipeline:
    # 1. Setup logging
    # 2. Load configuration
    # 3. Create sample data
    # 4. Validate data
    # 5. Process data
    # 6. Log results

    log = structlog.get_logger()
    log.info("pipeline_started")

    # Your code here...

    log.info("pipeline_completed")

if __name__ == "__main__":
    main()
```

### Expected Output

```bash
$ python starter/pipeline.py

{"event": "pipeline_started", "timestamp": "2025-11-13T12:00:00Z"}
{"event": "interactions_created", "count": 10, "timestamp": "2025-11-13T12:00:01Z"}
{"event": "validation_complete", "valid": 10, "invalid": 0, "timestamp": "2025-11-13T12:00:02Z"}
{"event": "processing_complete", "total_tokens": 15234, "total_cost": 0.45, "avg_latency_ms": 423.5, "timestamp": "2025-11-13T12:00:03Z"}
{"event": "pipeline_completed", "timestamp": "2025-11-13T12:00:04Z"}
```

---

## ✅ Exercises

### Beginner

1. **Exercise 1.1**: Create Book model with validation (15 min)
2. **Exercise 1.2**: Implement LLMInteraction model (30 min)
3. **Exercise 1.3**: Build configuration system (20 min)
4. **Exercise 1.4**: Setup structured logging (15 min)
5. **Exercise 1.5**: Write basic tests (30 min)

### Intermediate

6. **Exercise 1.6**: Add custom validators for email, URL, phone (20 min)
7. **Exercise 1.7**: Create EmbeddingResponse model (30 min)
8. **Exercise 1.8**: Add configuration validation (25 min)
9. **Exercise 1.9**: Write parametrized tests (30 min)
10. **Exercise 1.10**: Add logging to all models (20 min)

### Advanced

11. **Exercise 1.11**: Implement model serialization/deserialization (45 min)
12. **Exercise 1.12**: Create model factory functions (30 min)
13. **Exercise 1.13**: Add custom JSON encoders (40 min)
14. **Exercise 1.14**: Implement model versioning (60 min)
15. **Mini-Project**: Complete data pipeline (120 min)

---

## 📊 Progress Checklist

Track your progress:

- [ ] Read and understand Pydantic V2 basics
- [ ] Complete Exercise 1.1 (Book model)
- [ ] Complete Exercise 1.2 (LLMInteraction model)
- [ ] Complete Exercise 1.3 (Configuration system)
- [ ] Complete Exercise 1.4 (Structured logging)
- [ ] Complete Exercise 1.5 (Basic tests)
- [ ] All tests passing (`pytest ../tests/ -v`)
- [ ] Code coverage > 80% (`pytest --cov`)
- [ ] Mini-project complete
- [ ] Understand all concepts
- [ ] Ready for Week 2!

---

## 📚 Resources

### Documentation
- [Pydantic V2 Docs](https://docs.pydantic.dev/latest/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [structlog Docs](https://www.structlog.org/)
- [pytest Docs](https://docs.pytest.org/)

### Tutorials
- [Real Python: Pydantic](https://realpython.com/python-pydantic/)
- [Real Python: pytest](https://realpython.com/pytest-python-testing/)

### Videos
- [ArjanCodes: Pydantic V2](https://www.youtube.com/watch?v=yj-wSRJwrrc)
- [mCoding: pytest](https://www.youtube.com/watch?v=cHYq1MRoyI0)

---

## 🎯 Next Week Preview

In **Week 2: Storage Layer**, you'll build:
- DuckDB analytical storage
- Redis caching layer
- Delta Lake S3 integration
- Comprehensive storage tests

Get ready to level up! 🚀

---

## 💡 Tips

1. **Read the production code first** - Understand what you're building
2. **Run tests frequently** - TDD: Red → Green → Refactor
3. **Use type hints** - They help catch errors early
4. **Read error messages** - Pydantic errors are very helpful
5. **Ask questions** - Understanding > Speed

**Good luck! You've got this! 💪**
