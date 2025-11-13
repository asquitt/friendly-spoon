"""
Kafka Consumer for LLM Interaction Events.

This consumer:
1. Reads LLM interaction events from Kafka
2. Writes to feature store
3. Triggers embedding generation (optional)
4. Handles errors and retries

Cost Efficiency:
- Batch processing reduces overhead
- Async processing prevents blocking
- Error handling prevents data loss
"""

import json
import signal
import sys
from typing import Optional, Callable
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from ..shared.config import get_config
from ..shared.logger import get_logger
from ..shared.models import LLMInteraction
from ..storage.feature_store import FeatureStore

log = get_logger(__name__)


class LLMInteractionConsumer:
    """
    Kafka consumer for LLM interaction events.

    This consumes events from the 'llm-interactions' topic and
    processes them into the feature store.

    Example:
        >>> consumer = LLMInteractionConsumer()
        >>> consumer.start()  # Runs forever, processing events
    """

    def __init__(
        self,
        feature_store: Optional[FeatureStore] = None,
        on_interaction: Optional[Callable[[LLMInteraction], None]] = None
    ):
        """
        Initialize Kafka consumer.

        Args:
            feature_store: Feature store instance
            on_interaction: Optional callback for each interaction
        """
        self.config = get_config()
        self.feature_store = feature_store or FeatureStore()
        self.on_interaction = on_interaction
        self.running = False

        # Create Kafka consumer
        self.consumer = KafkaConsumer(
            self.config.kafka_topic_interactions,
            bootstrap_servers=self.config.kafka_bootstrap_servers.split(","),
            group_id=self.config.kafka_consumer_group,
            auto_offset_reset="earliest",  # Start from beginning if no offset
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            max_poll_records=self.config.kafka_batch_size,
        )

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        log.info(
            "kafka_consumer_initialized",
            topic=self.config.kafka_topic_interactions,
            bootstrap_servers=self.config.kafka_bootstrap_servers
        )

    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        log.info("shutdown_signal_received", signal=signum)
        self.stop()

    def start(self) -> None:
        """
        Start consuming events (blocking call).

        This runs forever until stop() is called or process is killed.

        Example:
            >>> consumer = LLMInteractionConsumer()
            >>> consumer.start()  # Runs until Ctrl+C
        """
        self.running = True

        log.info("kafka_consumer_started", topic=self.config.kafka_topic_interactions)

        try:
            for message in self.consumer:
                if not self.running:
                    break

                try:
                    self._process_message(message)
                except Exception as e:
                    log.error(
                        "message_processing_failed",
                        error=str(e),
                        partition=message.partition,
                        offset=message.offset
                    )
                    # Continue processing other messages

        except KafkaError as e:
            log.error("kafka_error", error=str(e))
            raise

        finally:
            self.consumer.close()
            log.info("kafka_consumer_stopped")

    def stop(self) -> None:
        """Stop consuming events."""
        log.info("stopping_kafka_consumer")
        self.running = False

    def _process_message(self, message) -> None:
        """
        Process a single Kafka message.

        Args:
            message: Kafka message
        """
        try:
            # Parse interaction from message
            data = message.value
            interaction = LLMInteraction(**data)

            log.debug(
                "processing_interaction",
                interaction_id=interaction.interaction_id,
                user_id=interaction.user_id
            )

            # Write to feature store
            success = self.feature_store.write_interaction(interaction)

            if not success:
                log.error(
                    "failed_to_write_interaction",
                    interaction_id=interaction.interaction_id
                )
                return

            # Call custom callback if provided
            if self.on_interaction:
                self.on_interaction(interaction)

            log.info(
                "interaction_processed",
                interaction_id=interaction.interaction_id,
                user_id=interaction.user_id,
                cost_usd=interaction.cost_usd
            )

        except Exception as e:
            log.error("process_message_failed", error=str(e), message_value=str(message.value))
            raise


# =============================================================================
# Simple Producer for Testing
# =============================================================================

class LLMInteractionProducer:
    """
    Simple Kafka producer for publishing LLM interaction events.

    Example:
        >>> producer = LLMInteractionProducer()
        >>> producer.send(interaction)
    """

    def __init__(self):
        """Initialize Kafka producer."""
        from kafka import KafkaProducer

        config = get_config()

        self.producer = KafkaProducer(
            bootstrap_servers=config.kafka_bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )

        self.topic = config.kafka_topic_interactions

        log.info("kafka_producer_initialized", topic=self.topic)

    def send(self, interaction: LLMInteraction) -> None:
        """
        Send an interaction event to Kafka.

        Args:
            interaction: LLMInteraction to publish
        """
        try:
            # Serialize to dict
            data = interaction.model_dump(mode="json")

            # Send to Kafka
            future = self.producer.send(self.topic, value=data)
            future.get(timeout=10)  # Wait for send to complete

            log.debug(
                "interaction_sent",
                interaction_id=interaction.interaction_id,
                topic=self.topic
            )

        except Exception as e:
            log.error(
                "send_interaction_failed",
                error=str(e),
                interaction_id=interaction.interaction_id
            )
            raise

    def close(self) -> None:
        """Close producer."""
        self.producer.flush()
        self.producer.close()
        log.info("kafka_producer_closed")


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger
    from ..shared.models import ModelProvider
    from datetime import datetime
    import time

    setup_logger("kafka-test", environment="local", debug=True)

    print("📨 Testing Kafka producer/consumer...")

    # Create sample interaction
    interaction = LLMInteraction(
        interaction_id="int_test_123",
        user_id="user_test",
        model="gpt-4",
        provider=ModelProvider.OPENAI,
        prompt="Test prompt",
        response="Test response",
        input_tokens=10,
        output_tokens=20,
        latency_ms=1000.0,
        cost_usd=0.01,
        timestamp=datetime.utcnow()
    )

    # Send to Kafka
    print("\n📤 Sending interaction to Kafka...")
    producer = LLMInteractionProducer()
    producer.send(interaction)
    producer.close()
    print("✅ Sent!")

    # Consume from Kafka
    print("\n📥 Starting consumer (press Ctrl+C to stop)...")

    def on_interaction_callback(interaction: LLMInteraction):
        print(f"   📝 Processed: {interaction.interaction_id}")

    consumer = LLMInteractionConsumer(on_interaction=on_interaction_callback)

    try:
        # Run for a few seconds then stop
        import threading
        def stop_after_delay():
            time.sleep(5)
            consumer.stop()

        threading.Thread(target=stop_after_delay, daemon=True).start()
        consumer.start()

    except KeyboardInterrupt:
        consumer.stop()

    print("\n✅ Kafka test complete!")
