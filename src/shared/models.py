"""
Data Models for LLM Feature Store.

This module defines Pydantic models for:
- LLM interactions (prompts, responses, metadata)
- Features (computed values, embeddings)
- Embedding requests/responses
- Cost tracking data

Why Pydantic?
- Automatic validation (catch errors early)
- Type safety (better IDE support)
- Easy serialization to/from JSON
- Self-documenting code
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


# =============================================================================
# Enums for Type Safety
# =============================================================================

class ModelProvider(str, Enum):
    """LLM model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"


class FeatureType(str, Enum):
    """Types of features we track."""
    EMBEDDING = "embedding"          # Vector embeddings
    NUMERIC = "numeric"              # Numbers (latency, token count, etc.)
    CATEGORICAL = "categorical"       # Categories (model, provider, etc.)
    TEXT = "text"                    # Raw text (prompts, responses)
    COST = "cost"                    # Cost-related metrics


class DriftStatus(str, Enum):
    """Feature drift detection status."""
    NO_DRIFT = "no_drift"            # Feature is stable
    WARNING = "warning"              # Minor drift detected
    CRITICAL = "critical"            # Significant drift detected


# =============================================================================
# Core Data Models
# =============================================================================

class LLMInteraction(BaseModel):
    """
    Represents a single interaction with an LLM.

    This is the primary event that flows through the system. Each interaction
    generates features that are stored and monitored.

    Example:
        >>> interaction = LLMInteraction(
        ...     interaction_id="int_123",
        ...     user_id="user_456",
        ...     session_id="sess_789",
        ...     model="gpt-4",
        ...     provider=ModelProvider.OPENAI,
        ...     prompt="What is machine learning?",
        ...     response="Machine learning is...",
        ...     input_tokens=5,
        ...     output_tokens=50,
        ...     latency_ms=1200.5,
        ...     cost_usd=0.006
        ... )
    """

    # Identifiers
    interaction_id: str = Field(
        ...,
        description="Unique interaction ID"
    )

    user_id: str = Field(
        ...,
        description="User who made the request"
    )

    session_id: Optional[str] = Field(
        None,
        description="Session ID for grouping related interactions"
    )

    # Model information
    model: str = Field(
        ...,
        description="Model name (e.g., 'gpt-4', 'claude-3-sonnet')"
    )

    provider: ModelProvider = Field(
        ...,
        description="Model provider"
    )

    # Content
    prompt: str = Field(
        ...,
        description="User's input prompt"
    )

    response: str = Field(
        ...,
        description="Model's response"
    )

    # Metrics
    input_tokens: int = Field(
        ...,
        ge=0,
        description="Number of input tokens"
    )

    output_tokens: int = Field(
        ...,
        ge=0,
        description="Number of output tokens"
    )

    latency_ms: float = Field(
        ...,
        ge=0,
        description="Response latency in milliseconds"
    )

    cost_usd: float = Field(
        ...,
        ge=0,
        description="Cost of this interaction in USD"
    )

    # Timestamps
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this interaction occurred"
    )

    # Metadata (for extensibility)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (tags, experiment IDs, etc.)"
    )

    @field_validator('prompt')
    @classmethod
    def prompt_not_empty(cls, v):
        """Ensure prompt is not empty."""
        if not v or not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def cost_per_token(self) -> float:
        """Cost per token for this interaction."""
        total = self.total_tokens
        return self.cost_usd / total if total > 0 else 0.0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "interaction_id": "int_abc123",
                "user_id": "user_456",
                "session_id": "sess_789",
                "model": "gpt-4",
                "provider": "openai",
                "prompt": "What is machine learning?",
                "response": "Machine learning is a subset of AI...",
                "input_tokens": 5,
                "output_tokens": 50,
                "latency_ms": 1200.5,
                "cost_usd": 0.006,
                "metadata": {"experiment": "A/B test v2"}
            }
        }
    )


class Feature(BaseModel):
    """
    Represents a computed feature value.

    Features are derived from LLM interactions and stored for:
    - Real-time serving (low-latency lookups)
    - Analytics (trend analysis, reporting)
    - ML training (as input features)

    Example:
        >>> feature = Feature(
        ...     feature_name="avg_prompt_length_7d",
        ...     entity_id="user_456",
        ...     value=125.5,
        ...     feature_type=FeatureType.NUMERIC,
        ... )
    """

    # Identification
    feature_name: str = Field(
        ...,
        description="Name of the feature (e.g., 'avg_tokens_per_request')"
    )

    entity_id: str = Field(
        ...,
        description="Entity this feature belongs to (user_id, session_id, etc.)"
    )

    # Value
    value: Any = Field(
        ...,
        description="Feature value (can be number, string, list, etc.)"
    )

    feature_type: FeatureType = Field(
        ...,
        description="Type of feature"
    )

    # Timestamps
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this feature was computed"
    )

    # Metadata
    version: int = Field(
        default=1,
        description="Feature version (for tracking changes)"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feature_name": "avg_prompt_length_7d",
                "entity_id": "user_456",
                "value": 125.5,
                "feature_type": "numeric",
                "version": 1,
                "metadata": {"window": "7d", "computation_time_ms": 45}
            }
        }
    )


class EmbeddingRequest(BaseModel):
    """
    Request to generate an embedding.

    This is published to Kafka and processed by the embedding service.

    Example:
        >>> request = EmbeddingRequest(
        ...     request_id="emb_req_123",
        ...     text="What is machine learning?",
        ...     model="all-MiniLM-L6-v2",
        ... )
    """

    request_id: str = Field(
        ...,
        description="Unique request ID"
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Text to embed"
    )

    model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model to use"
    )

    # Context for tracking
    entity_id: Optional[str] = Field(
        None,
        description="Entity ID (user, session, etc.) for tracking"
    )

    interaction_id: Optional[str] = Field(
        None,
        description="Related interaction ID"
    )

    # Caching hint
    cache_ttl: Optional[int] = Field(
        None,
        description="Cache TTL in seconds (None = use default)"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Request timestamp"
    )


class EmbeddingResponse(BaseModel):
    """
    Response containing generated embedding.

    Example:
        >>> response = EmbeddingResponse(
        ...     request_id="emb_req_123",
        ...     embedding=[0.1, 0.2, -0.3, ...],  # 384 dimensions
        ...     model="all-MiniLM-L6-v2",
        ...     cache_hit=False,
        ...     latency_ms=45.2
        ... )
    """

    request_id: str = Field(
        ...,
        description="Request ID (matches EmbeddingRequest)"
    )

    embedding: List[float] = Field(
        ...,
        description="Vector embedding (list of floats)"
    )

    model: str = Field(
        ...,
        description="Model used to generate embedding"
    )

    # Performance metrics
    cache_hit: bool = Field(
        ...,
        description="Whether embedding was served from cache"
    )

    latency_ms: float = Field(
        ...,
        ge=0,
        description="Generation latency in milliseconds"
    )

    cost_usd: float = Field(
        default=0.0,
        ge=0,
        description="Cost of generation (0 for local models)"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )

    @field_validator('embedding')
    @classmethod
    def validate_embedding(cls, v):
        """Ensure embedding is not empty."""
        if not v:
            raise ValueError("Embedding cannot be empty")
        return v

    @property
    def dimension(self) -> int:
        """Embedding dimension."""
        return len(self.embedding)


class DriftDetectionResult(BaseModel):
    """
    Result of feature drift detection.

    Drift detection helps you know when your LLM's behavior changes
    significantly, which might require retraining or investigation.

    Example:
        >>> result = DriftDetectionResult(
        ...     feature_name="avg_prompt_length",
        ...     entity_id="all_users",
        ...     drift_status=DriftStatus.WARNING,
        ...     drift_score=0.15,
        ...     threshold=0.1,
        ...     historical_mean=100.5,
        ...     current_mean=115.2,
        ... )
    """

    # Identification
    feature_name: str = Field(
        ...,
        description="Feature being monitored"
    )

    entity_id: str = Field(
        ...,
        description="Entity ID (or 'all' for global)"
    )

    # Drift metrics
    drift_status: DriftStatus = Field(
        ...,
        description="Drift severity"
    )

    drift_score: float = Field(
        ...,
        ge=0,
        description="Drift score (e.g., PSI, KS statistic)"
    )

    threshold: float = Field(
        ...,
        ge=0,
        description="Threshold for drift detection"
    )

    # Statistical details
    historical_mean: Optional[float] = Field(
        None,
        description="Historical mean value"
    )

    current_mean: Optional[float] = Field(
        None,
        description="Current mean value"
    )

    historical_std: Optional[float] = Field(
        None,
        description="Historical standard deviation"
    )

    current_std: Optional[float] = Field(
        None,
        description="Current standard deviation"
    )

    # Timestamps
    detection_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="When drift was detected"
    )

    window_start: datetime = Field(
        ...,
        description="Start of comparison window"
    )

    window_end: datetime = Field(
        ...,
        description="End of comparison window"
    )

    # Metadata
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional details (test results, etc.)"
    )

    @property
    def drift_detected(self) -> bool:
        """Whether drift was detected."""
        return self.drift_status != DriftStatus.NO_DRIFT

    @property
    def mean_change_percent(self) -> Optional[float]:
        """Percentage change in mean value."""
        if self.historical_mean and self.current_mean:
            return (
                (self.current_mean - self.historical_mean) /
                self.historical_mean * 100
            )
        return None


class CostSummary(BaseModel):
    """
    Summary of LLM costs for a time period.

    This helps answer questions like:
    - How much did we spend today?
    - Which model is most expensive?
    - Which user is driving the most cost?

    Example:
        >>> summary = CostSummary(
        ...     period_start=datetime(2025, 1, 1),
        ...     period_end=datetime(2025, 1, 31),
        ...     total_cost_usd=125.50,
        ...     total_tokens=5_000_000,
        ...     total_interactions=10_000,
        ...     cost_by_model={"gpt-4": 100.0, "gpt-3.5-turbo": 25.5},
        ... )
    """

    # Time period
    period_start: datetime = Field(
        ...,
        description="Start of period"
    )

    period_end: datetime = Field(
        ...,
        description="End of period"
    )

    # Totals
    total_cost_usd: float = Field(
        ...,
        ge=0,
        description="Total cost in USD"
    )

    total_tokens: int = Field(
        ...,
        ge=0,
        description="Total tokens used"
    )

    total_interactions: int = Field(
        ...,
        ge=0,
        description="Total LLM interactions"
    )

    # Breakdowns
    cost_by_model: Dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by model"
    )

    cost_by_user: Dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by user"
    )

    # Cache savings
    cache_hit_rate: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Cache hit rate (0-1)"
    )

    cost_saved_by_cache: Optional[float] = Field(
        None,
        ge=0,
        description="Money saved by caching (USD)"
    )

    @property
    def avg_cost_per_interaction(self) -> float:
        """Average cost per interaction."""
        if self.total_interactions > 0:
            return self.total_cost_usd / self.total_interactions
        return 0.0

    @property
    def avg_tokens_per_interaction(self) -> float:
        """Average tokens per interaction."""
        if self.total_interactions > 0:
            return self.total_tokens / self.total_interactions
        return 0.0


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Create sample interaction
    interaction = LLMInteraction(
        interaction_id="int_123",
        user_id="user_456",
        model="gpt-4",
        provider=ModelProvider.OPENAI,
        prompt="What is machine learning?",
        response="Machine learning is a subset of AI...",
        input_tokens=5,
        output_tokens=50,
        latency_ms=1200.5,
        cost_usd=0.006,
    )

    print("📝 Sample LLM Interaction:")
    print(interaction.model_dump_json(indent=2))
    print(f"\n💰 Cost per token: ${interaction.cost_per_token:.6f}")

    # Create sample embedding request
    embedding_req = EmbeddingRequest(
        request_id="emb_123",
        text="What is machine learning?",
        model="all-MiniLM-L6-v2",
    )

    print("\n🔢 Sample Embedding Request:")
    print(embedding_req.model_dump_json(indent=2))

    # Create sample drift detection result
    drift = DriftDetectionResult(
        feature_name="avg_prompt_length",
        entity_id="all_users",
        drift_status=DriftStatus.WARNING,
        drift_score=0.15,
        threshold=0.1,
        historical_mean=100.5,
        current_mean=115.2,
        window_start=datetime(2025, 1, 1),
        window_end=datetime(2025, 1, 7),
    )

    print("\n⚠️  Sample Drift Detection:")
    print(drift.model_dump_json(indent=2))
    print(f"\n📊 Mean change: {drift.mean_change_percent:.1f}%")
