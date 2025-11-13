"""
Unit tests for data models.

Tests cover:
- Model validation
- Property calculations
- Edge cases
- Serialization/deserialization
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.shared.models import (
    LLMInteraction,
    ModelProvider,
    Feature,
    FeatureType,
    EmbeddingRequest,
    EmbeddingResponse,
    DriftDetectionResult,
    DriftStatus,
    CostSummary
)


class TestLLMInteraction:
    """Test cases for LLMInteraction model."""

    def test_valid_interaction_creation(self, sample_interaction):
        """Test creating a valid interaction."""
        assert sample_interaction.interaction_id == "test_int_001"
        assert sample_interaction.user_id == "test_user_001"
        assert sample_interaction.model == "gpt-4"
        assert sample_interaction.input_tokens == 5
        assert sample_interaction.output_tokens == 15

    def test_total_tokens_property(self, sample_interaction):
        """Test total_tokens calculation."""
        assert sample_interaction.total_tokens == 20
        assert sample_interaction.total_tokens == sample_interaction.input_tokens + sample_interaction.output_tokens

    def test_cost_per_token_property(self, sample_interaction):
        """Test cost_per_token calculation."""
        expected = sample_interaction.cost_usd / sample_interaction.total_tokens
        assert abs(sample_interaction.cost_per_token - expected) < 0.0001

    def test_cost_per_token_zero_tokens(self):
        """Test cost_per_token with zero tokens."""
        interaction = LLMInteraction(
            interaction_id="test",
            user_id="user",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt="test",
            response="test",
            input_tokens=0,
            output_tokens=0,
            latency_ms=100,
            cost_usd=0.0
        )
        assert interaction.cost_per_token == 0.0

    def test_empty_prompt_validation(self):
        """Test that empty prompts are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LLMInteraction(
                interaction_id="test",
                user_id="user",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt="",  # Empty prompt
                response="test",
                input_tokens=5,
                output_tokens=10,
                latency_ms=100,
                cost_usd=0.01
            )

        assert "Prompt cannot be empty" in str(exc_info.value)

    def test_negative_tokens_validation(self):
        """Test that negative token counts are rejected."""
        with pytest.raises(ValidationError):
            LLMInteraction(
                interaction_id="test",
                user_id="user",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt="test",
                response="test",
                input_tokens=-5,  # Negative
                output_tokens=10,
                latency_ms=100,
                cost_usd=0.01
            )

    def test_json_serialization(self, sample_interaction):
        """Test serialization to JSON."""
        json_data = sample_interaction.model_dump_json()
        assert "test_int_001" in json_data
        assert "gpt-4" in json_data

    def test_json_deserialization(self, sample_interaction):
        """Test deserialization from JSON."""
        json_data = sample_interaction.model_dump()
        reconstructed = LLMInteraction(**json_data)

        assert reconstructed.interaction_id == sample_interaction.interaction_id
        assert reconstructed.cost_usd == sample_interaction.cost_usd

    def test_metadata_field(self):
        """Test optional metadata field."""
        interaction = LLMInteraction(
            interaction_id="test",
            user_id="user",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt="test",
            response="test",
            input_tokens=5,
            output_tokens=10,
            latency_ms=100,
            cost_usd=0.01,
            metadata={"experiment": "A/B test", "version": "v2"}
        )

        assert interaction.metadata["experiment"] == "A/B test"
        assert interaction.metadata["version"] == "v2"


class TestFeature:
    """Test cases for Feature model."""

    def test_feature_creation(self):
        """Test creating a feature."""
        feature = Feature(
            feature_name="avg_tokens",
            entity_id="user_123",
            value=150.5,
            feature_type=FeatureType.NUMERIC
        )

        assert feature.feature_name == "avg_tokens"
        assert feature.value == 150.5
        assert feature.feature_type == FeatureType.NUMERIC

    def test_feature_versioning(self):
        """Test feature version tracking."""
        feature = Feature(
            feature_name="test_feature",
            entity_id="user_123",
            value=100,
            feature_type=FeatureType.NUMERIC,
            version=2
        )

        assert feature.version == 2

    def test_feature_with_list_value(self):
        """Test feature with list value (e.g., embedding)."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        feature = Feature(
            feature_name="prompt_embedding",
            entity_id="user_123",
            value=embedding,
            feature_type=FeatureType.EMBEDDING
        )

        assert feature.value == embedding
        assert len(feature.value) == 4


class TestEmbeddingRequest:
    """Test cases for EmbeddingRequest model."""

    def test_valid_request(self, sample_embedding_request):
        """Test creating a valid embedding request."""
        assert sample_embedding_request.request_id == "test_emb_req_001"
        assert sample_embedding_request.text == "What is machine learning?"
        assert sample_embedding_request.model == "all-MiniLM-L6-v2"

    def test_empty_text_validation(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValidationError):
            EmbeddingRequest(
                request_id="test",
                text="",  # Empty text
                model="all-MiniLM-L6-v2"
            )

    def test_optional_fields(self):
        """Test optional fields have defaults."""
        request = EmbeddingRequest(
            request_id="test",
            text="test text"
        )

        assert request.model == "all-MiniLM-L6-v2"  # Default model
        assert request.entity_id is None
        assert request.cache_ttl is None


class TestEmbeddingResponse:
    """Test cases for EmbeddingResponse model."""

    def test_valid_response(self):
        """Test creating a valid embedding response."""
        embedding = [0.1] * 384  # 384-dimensional embedding

        response = EmbeddingResponse(
            request_id="test_req",
            embedding=embedding,
            model="all-MiniLM-L6-v2",
            cache_hit=False,
            latency_ms=45.2,
            cost_usd=0.0
        )

        assert response.dimension == 384
        assert response.cache_hit is False
        assert response.cost_usd == 0.0

    def test_empty_embedding_validation(self):
        """Test that empty embeddings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingResponse(
                request_id="test",
                embedding=[],  # Empty
                model="all-MiniLM-L6-v2",
                cache_hit=False,
                latency_ms=10,
                cost_usd=0.0
            )

        assert "Embedding cannot be empty" in str(exc_info.value)

    def test_dimension_property(self):
        """Test dimension property calculation."""
        embedding = [0.1] * 768

        response = EmbeddingResponse(
            request_id="test",
            embedding=embedding,
            model="test-model",
            cache_hit=False,
            latency_ms=10,
            cost_usd=0.0
        )

        assert response.dimension == 768


class TestDriftDetectionResult:
    """Test cases for DriftDetectionResult model."""

    def test_drift_detected_property(self):
        """Test drift_detected property."""
        # No drift
        result_no_drift = DriftDetectionResult(
            feature_name="test_feature",
            entity_id="all",
            drift_status=DriftStatus.NO_DRIFT,
            drift_score=0.05,
            threshold=0.1,
            window_start=datetime(2025, 1, 1),
            window_end=datetime(2025, 1, 7)
        )

        assert result_no_drift.drift_detected is False

        # Warning drift
        result_warning = DriftDetectionResult(
            feature_name="test_feature",
            entity_id="all",
            drift_status=DriftStatus.WARNING,
            drift_score=0.15,
            threshold=0.1,
            window_start=datetime(2025, 1, 1),
            window_end=datetime(2025, 1, 7)
        )

        assert result_warning.drift_detected is True

    def test_mean_change_percent(self):
        """Test mean change percentage calculation."""
        result = DriftDetectionResult(
            feature_name="test_feature",
            entity_id="all",
            drift_status=DriftStatus.WARNING,
            drift_score=0.15,
            threshold=0.1,
            historical_mean=100.0,
            current_mean=120.0,
            window_start=datetime(2025, 1, 1),
            window_end=datetime(2025, 1, 7)
        )

        assert result.mean_change_percent == 20.0

    def test_mean_change_with_none_values(self):
        """Test mean change when values are None."""
        result = DriftDetectionResult(
            feature_name="test_feature",
            entity_id="all",
            drift_status=DriftStatus.NO_DRIFT,
            drift_score=0.05,
            threshold=0.1,
            historical_mean=None,
            current_mean=None,
            window_start=datetime(2025, 1, 1),
            window_end=datetime(2025, 1, 7)
        )

        assert result.mean_change_percent is None


class TestCostSummary:
    """Test cases for CostSummary model."""

    def test_avg_cost_per_interaction(self):
        """Test average cost calculation."""
        summary = CostSummary(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 31),
            total_cost_usd=100.0,
            total_tokens=1_000_000,
            total_interactions=10_000
        )

        assert summary.avg_cost_per_interaction == 0.01

    def test_avg_cost_with_zero_interactions(self):
        """Test average cost with zero interactions."""
        summary = CostSummary(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 31),
            total_cost_usd=0.0,
            total_tokens=0,
            total_interactions=0
        )

        assert summary.avg_cost_per_interaction == 0.0

    def test_avg_tokens_per_interaction(self):
        """Test average tokens calculation."""
        summary = CostSummary(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 31),
            total_cost_usd=100.0,
            total_tokens=1_000_000,
            total_interactions=10_000
        )

        assert summary.avg_tokens_per_interaction == 100.0

    def test_cache_hit_rate_validation(self):
        """Test cache hit rate is between 0 and 1."""
        # Valid
        summary = CostSummary(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 31),
            total_cost_usd=100.0,
            total_tokens=1_000_000,
            total_interactions=10_000,
            cache_hit_rate=0.95
        )

        assert summary.cache_hit_rate == 0.95

        # Invalid (>1)
        with pytest.raises(ValidationError):
            CostSummary(
                period_start=datetime(2025, 1, 1),
                period_end=datetime(2025, 1, 31),
                total_cost_usd=100.0,
                total_tokens=1_000_000,
                total_interactions=10_000,
                cache_hit_rate=1.5  # Invalid
            )


# =============================================================================
# Parametrized Tests
# =============================================================================

@pytest.mark.parametrize("input_tokens,output_tokens,expected_total", [
    (10, 20, 30),
    (0, 100, 100),
    (100, 0, 100),
    (1, 1, 2),
    (1000, 2000, 3000),
])
def test_total_tokens_various_inputs(input_tokens, output_tokens, expected_total):
    """Test total tokens calculation with various inputs."""
    interaction = LLMInteraction(
        interaction_id="test",
        user_id="user",
        model="gpt-4",
        provider=ModelProvider.OPENAI,
        prompt="test",
        response="test",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=100,
        cost_usd=0.01
    )

    assert interaction.total_tokens == expected_total


@pytest.mark.parametrize("provider", [
    ModelProvider.OPENAI,
    ModelProvider.ANTHROPIC,
    ModelProvider.COHERE,
    ModelProvider.HUGGINGFACE,
    ModelProvider.LOCAL,
])
def test_all_providers(provider):
    """Test interaction creation with all provider types."""
    interaction = LLMInteraction(
        interaction_id="test",
        user_id="user",
        model="test-model",
        provider=provider,
        prompt="test",
        response="test",
        input_tokens=10,
        output_tokens=20,
        latency_ms=100,
        cost_usd=0.01
    )

    assert interaction.provider == provider
