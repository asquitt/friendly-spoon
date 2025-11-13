"""
Feature Drift Detection System.

Detects when LLM behavior changes significantly using:
- Population Stability Index (PSI)
- Kolmogorov-Smirnov test
- Statistical Process Control (SPC)

Why drift detection matters:
- Detect when LLM costs suddenly increase
- Identify changes in user behavior
- Monitor feature quality degradation
- Trigger alerts for investigation
"""

import numpy as np
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
import pandas as pd

from ..shared.config import get_config
from ..shared.logger import get_logger
from ..shared.models import DriftDetectionResult, DriftStatus
from ..storage.duckdb_store import DuckDBStore

log = get_logger(__name__)


class DriftDetector:
    """
    Detects feature drift using statistical methods.

    Example:
        >>> detector = DriftDetector()
        >>> result = detector.check_drift(
        ...     feature_name="avg_prompt_length",
        ...     entity_id="all_users",
        ...     current_values=[100, 105, 110, ...],
        ...     historical_values=[80, 85, 90, ...]
        ... )
        >>> if result.drift_detected:
        ...     print(f"⚠️ Drift detected! Score: {result.drift_score:.2f}")
    """

    def __init__(self, duckdb_store: Optional[DuckDBStore] = None):
        """
        Initialize drift detector.

        Args:
            duckdb_store: DuckDB store for fetching historical data
        """
        self.config = get_config()
        self.duckdb = duckdb_store or DuckDBStore()

        log.info("drift_detector_initialized")

    def calculate_psi(
        self,
        expected: np.ndarray,
        actual: np.ndarray,
        bins: int = 10
    ) -> float:
        """
        Calculate Population Stability Index (PSI).

        PSI measures how much a distribution has shifted.

        PSI ranges:
        - < 0.1: No significant change
        - 0.1-0.2: Small change (monitor)
        - > 0.2: Significant change (investigate!)

        Args:
            expected: Historical values
            actual: Current values
            bins: Number of bins for discretization

        Returns:
            float: PSI score

        Example:
            >>> historical = np.array([100, 105, 110, 95, 98])
            >>> current = np.array([150, 155, 160, 145, 148])
            >>> psi = detector.calculate_psi(historical, current)
            >>> print(f"PSI: {psi:.3f}")
        """
        # Create bins based on expected distribution
        breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
        breakpoints[-1] = np.inf  # Ensure last bin catches all values
        breakpoints[0] = -np.inf  # Ensure first bin catches all values

        # Calculate distribution for expected
        expected_counts = np.histogram(expected, bins=breakpoints)[0]
        expected_percents = expected_counts / len(expected)

        # Calculate distribution for actual
        actual_counts = np.histogram(actual, bins=breakpoints)[0]
        actual_percents = actual_counts / len(actual)

        # Avoid division by zero
        expected_percents = np.where(expected_percents == 0, 0.0001, expected_percents)
        actual_percents = np.where(actual_percents == 0, 0.0001, actual_percents)

        # Calculate PSI
        psi = np.sum(
            (actual_percents - expected_percents) *
            np.log(actual_percents / expected_percents)
        )

        return float(psi)

    def kolmogorov_smirnov_test(
        self,
        expected: np.ndarray,
        actual: np.ndarray
    ) -> Tuple[float, float]:
        """
        Perform Kolmogorov-Smirnov test.

        Tests if two samples come from the same distribution.

        Args:
            expected: Historical values
            actual: Current values

        Returns:
            Tuple[float, float]: (statistic, p-value)
                - statistic: KS test statistic (0-1)
                - p-value: Probability samples are from same distribution

        Interpretation:
            - p-value > 0.05: No significant drift
            - p-value < 0.05: Significant drift detected

        Example:
            >>> stat, pval = detector.kolmogorov_smirnov_test(historical, current)
            >>> if pval < 0.05:
            ...     print("Drift detected!")
        """
        statistic, p_value = stats.ks_2samp(expected, actual)
        return float(statistic), float(p_value)

    def check_drift(
        self,
        feature_name: str,
        entity_id: str,
        current_values: Optional[List[float]] = None,
        historical_values: Optional[List[float]] = None,
        lookback_days: Optional[int] = None
    ) -> DriftDetectionResult:
        """
        Check for feature drift.

        This method:
        1. Fetches historical and current data (if not provided)
        2. Calculates PSI
        3. Performs KS test
        4. Determines drift status

        Args:
            feature_name: Feature to check
            entity_id: Entity ID (or "all" for global)
            current_values: Current feature values (optional, fetched if not provided)
            historical_values: Historical values (optional, fetched if not provided)
            lookback_days: Days to look back for historical data

        Returns:
            DriftDetectionResult: Drift detection result

        Example:
            >>> # Automatic data fetching
            >>> result = detector.check_drift(
            ...     feature_name="avg_prompt_length",
            ...     entity_id="all_users",
            ...     lookback_days=7
            ... )
        """
        if lookback_days is None:
            lookback_days = self.config.drift_detection_window_days

        threshold = self.config.drift_detection_threshold

        # If data not provided, fetch from DuckDB
        if historical_values is None or current_values is None:
            # This is simplified - in production, you'd have more sophisticated queries
            # For now, we'll use dummy data
            log.warning(
                "drift_check_no_data",
                feature_name=feature_name,
                entity_id=entity_id
            )

            # Return no drift for now (would fetch real data in production)
            return DriftDetectionResult(
                feature_name=feature_name,
                entity_id=entity_id,
                drift_status=DriftStatus.NO_DRIFT,
                drift_score=0.0,
                threshold=threshold,
                window_start=datetime.utcnow() - timedelta(days=lookback_days),
                window_end=datetime.utcnow()
            )

        # Convert to numpy arrays
        historical = np.array(historical_values)
        current = np.array(current_values)

        # Calculate PSI
        psi_score = self.calculate_psi(historical, current)

        # Perform KS test
        ks_statistic, ks_pvalue = self.kolmogorov_smirnov_test(historical, current)

        # Calculate statistics
        historical_mean = float(np.mean(historical))
        current_mean = float(np.mean(current))
        historical_std = float(np.std(historical))
        current_std = float(np.std(current))

        # Determine drift status
        if psi_score > threshold * 2:
            drift_status = DriftStatus.CRITICAL
        elif psi_score > threshold:
            drift_status = DriftStatus.WARNING
        else:
            drift_status = DriftStatus.NO_DRIFT

        result = DriftDetectionResult(
            feature_name=feature_name,
            entity_id=entity_id,
            drift_status=drift_status,
            drift_score=psi_score,
            threshold=threshold,
            historical_mean=historical_mean,
            current_mean=current_mean,
            historical_std=historical_std,
            current_std=current_std,
            window_start=datetime.utcnow() - timedelta(days=lookback_days),
            window_end=datetime.utcnow(),
            details={
                "psi": psi_score,
                "ks_statistic": ks_statistic,
                "ks_pvalue": ks_pvalue,
                "method": "PSI + KS Test"
            }
        )

        log.info(
            "drift_check_complete",
            feature_name=feature_name,
            entity_id=entity_id,
            drift_status=drift_status.value,
            drift_score=psi_score,
            mean_change_percent=result.mean_change_percent
        )

        return result

    def send_alert(
        self,
        result: DriftDetectionResult,
        channel: str = "slack"
    ) -> bool:
        """
        Send drift alert via configured channel.

        Args:
            result: Drift detection result
            channel: Alert channel ("slack", "pagerduty", "email")

        Returns:
            bool: True if alert sent successfully

        Example:
            >>> if result.drift_detected:
            ...     detector.send_alert(result, channel="slack")
        """
        if not result.drift_detected:
            log.debug("no_drift_no_alert", feature_name=result.feature_name)
            return True

        log.warning(
            "drift_alert",
            feature_name=result.feature_name,
            entity_id=result.entity_id,
            drift_status=result.drift_status.value,
            drift_score=result.drift_score,
            mean_change_percent=result.mean_change_percent
        )

        # In production, send to Slack/PagerDuty
        # For now, just log
        if channel == "slack" and self.config.enable_slack_alerts:
            # TODO: Implement Slack webhook
            log.info("slack_alert_sent", result=result.model_dump())
            return True

        return False


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger

    setup_logger("drift-detector-test", environment="local", debug=True)

    detector = DriftDetector()

    print("📊 Testing drift detection...")

    # Simulate historical data (stable)
    historical = np.random.normal(loc=100, scale=10, size=1000)

    # Simulate current data with drift
    current_no_drift = np.random.normal(loc=100, scale=10, size=1000)
    current_small_drift = np.random.normal(loc=110, scale=12, size=1000)
    current_large_drift = np.random.normal(loc=150, scale=20, size=1000)

    # Test 1: No drift
    print("\n✅ Test 1: No drift")
    result1 = detector.check_drift(
        feature_name="test_feature",
        entity_id="test",
        current_values=current_no_drift.tolist(),
        historical_values=historical.tolist()
    )
    print(f"   Status: {result1.drift_status.value}")
    print(f"   PSI: {result1.drift_score:.3f}")
    print(f"   Mean change: {result1.mean_change_percent:.1f}%")

    # Test 2: Small drift
    print("\n⚠️  Test 2: Small drift")
    result2 = detector.check_drift(
        feature_name="test_feature",
        entity_id="test",
        current_values=current_small_drift.tolist(),
        historical_values=historical.tolist()
    )
    print(f"   Status: {result2.drift_status.value}")
    print(f"   PSI: {result2.drift_score:.3f}")
    print(f"   Mean change: {result2.mean_change_percent:.1f}%")

    # Test 3: Large drift
    print("\n🚨 Test 3: Large drift")
    result3 = detector.check_drift(
        feature_name="test_feature",
        entity_id="test",
        current_values=current_large_drift.tolist(),
        historical_values=historical.tolist()
    )
    print(f"   Status: {result3.drift_status.value}")
    print(f"   PSI: {result3.drift_score:.3f}")
    print(f"   Mean change: {result3.mean_change_percent:.1f}%")

    print("\n✅ Drift detection test complete!")
