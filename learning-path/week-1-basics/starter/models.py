"""
Week 1 Starter: Data Models

Your task: Fill in the TODO comments to create robust data models with Pydantic V2.

Learning goals:
- Understand Pydantic BaseModel
- Implement field validation
- Create computed properties
- Use enums for constrained values
- Add helpful error messages

Run tests: pytest ../tests/test_models.py -v
"""

from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, date
from enum import Enum


# =============================================================================
# Exercise 1.1: Create a Book Model
# =============================================================================

class Book(BaseModel):
    """
    Model representing a book.

    Requirements:
    - title: string, 1-500 characters, required
    - author: string, 1-200 characters, required
    - pages: integer, must be > 0, required
    - isbn: optional string, 10 or 13 digits
    - price: float, must be >= 0, required
    - Validator: title cannot be just whitespace
    - Computed field: price_with_tax (price * 1.08)
    """

    # TODO: Add fields with proper types and validation
    # Hint: Use Field(..., min_length=X, max_length=Y) for string length
    # Hint: Use Field(..., ge=X) for "greater than or equal"

    # TODO: Add field validator for title
    # Hint: Use @field_validator('title') and @classmethod
    # Hint: Check if v.strip() is empty

    # TODO: Add computed property for price_with_tax
    # Hint: Use @computed_field and @property
    # Hint: Return self.price * 1.08

    # TODO: Add model configuration with an example
    # Hint: Use model_config = ConfigDict(json_schema_extra={...})

    pass  # Remove this when you add your code


# =============================================================================
# Enums for Constrained Values
# =============================================================================

class ModelProvider(str, Enum):
    """
    Supported LLM providers.

    Using Enum ensures only valid values can be used.
    """
    # TODO: Add enum values for:
    # - OPENAI = "openai"
    # - ANTHROPIC = "anthropic"
    # - GOOGLE = "google"
    # - META = "meta"
    # - COHERE = "cohere"
    # - OTHER = "other"

    pass  # Remove this when you add your code


# =============================================================================
# Exercise 1.2: LLM Interaction Model
# =============================================================================

class LLMInteraction(BaseModel):
    """
    Model for tracking LLM API interactions.

    This model captures everything about an LLM API call:
    - Identifiers (interaction_id, user_id)
    - Model information (model name, provider)
    - Content (prompt, response)
    - Metrics (tokens, latency, cost)
    - Metadata (timestamp, extra data)

    Requirements:
    - All string fields should have descriptions
    - Numeric fields should have >= 0 validation
    - Prompt and response cannot be empty
    - Computed fields for total_tokens and date
    """

    # === Identifiers ===
    # TODO: Add interaction_id field
    # Type: str, required, description: "Unique ID for this interaction"

    # TODO: Add user_id field
    # Type: str, required, description: "ID of the user making the request"

    # === Model Information ===
    # TODO: Add model field
    # Type: str, required, description: "Model name (e.g., 'gpt-4', 'claude-2')"

    # TODO: Add provider field
    # Type: ModelProvider (enum), required, description: "LLM provider"

    # === Content ===
    # TODO: Add prompt field
    # Type: str, required, description: "User prompt/input"

    # TODO: Add response field
    # Type: str, required, description: "LLM response/output"

    # === Metrics ===
    # TODO: Add input_tokens field
    # Type: int, required, >= 0, description: "Number of input tokens"

    # TODO: Add output_tokens field
    # Type: int, required, >= 0, description: "Number of output tokens"

    # TODO: Add latency_ms field
    # Type: float, required, >= 0, description: "Response time in milliseconds"

    # TODO: Add cost_usd field
    # Type: float, required, >= 0, description: "Cost in USD"

    # === Metadata ===
    # TODO: Add timestamp field
    # Type: datetime, default: current time, description: "When this happened"
    # Hint: Use Field(default_factory=datetime.now)

    # TODO: Add metadata field
    # Type: Optional[Dict[str, Any]], default: None, description: "Additional metadata"

    # === Computed Fields ===
    # TODO: Add computed property total_tokens
    # Should return: input_tokens + output_tokens
    # Hint: Use @computed_field and @property decorators

    # TODO: Add computed property date
    # Should return: date portion of timestamp (for partitioning)
    # Hint: Use self.timestamp.date()

    # === Validators ===
    # TODO: Add validator for prompt field
    # Should check: prompt is not empty or just whitespace
    # Should raise: ValueError("Prompt cannot be empty") if invalid
    # Hint: Use @field_validator('prompt') and @classmethod

    # TODO: Add validator for response field
    # Should check: response is not empty or just whitespace
    # Should raise: ValueError("Response cannot be empty") if invalid

    # === Configuration ===
    # TODO: Add model_config with json_schema_extra example
    # Include an example LLM interaction with all fields

    pass  # Remove this when you add your code


# =============================================================================
# Exercise 1.7: Embedding Response Model (Intermediate)
# =============================================================================

class EmbeddingResponse(BaseModel):
    """
    Model for embedding generation responses.

    Requirements:
    - text: the input text that was embedded
    - embedding: list of floats (the vector)
    - model: name of the embedding model used
    - dimension: computed from len(embedding)
    - cache_hit: boolean indicating if result was cached
    - latency_ms: time to generate (float, >= 0)
    """

    # TODO: Implement this model following the LLMInteraction example
    # Hint: Use List[float] for embedding field
    # Hint: computed_field for dimension
    # Hint: Add validation for embedding (must not be empty)

    pass  # Remove this when you add your code


# =============================================================================
# Helper Functions (for testing)
# =============================================================================

def create_sample_interaction() -> LLMInteraction:
    """
    Create a sample LLM interaction for testing.

    Returns:
        LLMInteraction: A valid sample interaction
    """
    # TODO: Create and return a sample LLMInteraction
    # Use realistic values for all fields
    # This is useful for testing and debugging

    pass  # Remove this when you add your code


def main():
    """
    Demo: Create and validate models.

    Run this file to test your implementations:
        python starter/models.py
    """
    print("=" * 80)
    print("Week 1: Data Models Demo")
    print("=" * 80)

    # TODO: Create a sample interaction and print it
    # interaction = create_sample_interaction()
    # print("\nSample Interaction:")
    # print(interaction.model_dump_json(indent=2))

    # TODO: Try creating invalid data (should raise validation errors)
    # try:
    #     bad_interaction = LLMInteraction(
    #         interaction_id="test",
    #         user_id="user1",
    #         model="gpt-4",
    #         provider=ModelProvider.OPENAI,
    #         prompt="",  # Empty! Should fail validation
    #         response="test",
    #         input_tokens=10,
    #         output_tokens=20,
    #         latency_ms=100.0,
    #         cost_usd=0.01
    #     )
    # except ValidationError as e:
    #     print("\nExpected validation error:")
    #     print(e)

    print("\n✅ If you see output above, your models are working!")
    print("Run tests with: pytest ../tests/test_models.py -v")


if __name__ == "__main__":
    main()
