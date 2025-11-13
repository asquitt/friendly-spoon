#!/usr/bin/env python
"""
Performance Benchmarking Script for LLM Feature Store

This script benchmarks critical operations and generates visualizations:
- DuckDB query performance
- Cache operations
- Data insertion throughput
- Memory usage

Usage:
    python benchmark_performance.py
    python benchmark_performance.py --quick        # Run quick benchmarks
    python benchmark_performance.py --detailed     # Run detailed benchmarks
    python benchmark_performance.py --visualize    # Generate charts
"""

import time
import sys
import argparse
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import json

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not installed. Some features disabled.")

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib/seaborn not installed. Visualization disabled.")

# Import project modules
from src.storage.duckdb_store import DuckDBStore
from src.shared.models import LLMInteraction, ModelProvider


class PerformanceBenchmark:
    """Performance benchmarking suite for LLM Feature Store."""

    def __init__(self, quick: bool = False):
        """Initialize benchmark suite."""
        self.quick = quick
        self.results: Dict[str, Dict] = {}

        # Benchmark parameters
        if quick:
            self.num_records = 100
            self.num_queries = 50
        else:
            self.num_records = 1000
            self.num_queries = 200

        print(f"Initializing benchmarks (quick={quick})")
        print(f"  - Records to insert: {self.num_records}")
        print(f"  - Queries to run: {self.num_queries}")
        print()

    def run_all(self) -> Dict:
        """Run all benchmarks."""
        print("=" * 80)
        print("PERFORMANCE BENCHMARK SUITE")
        print("=" * 80)
        print()

        # 1. DuckDB Benchmarks
        self.benchmark_duckdb_operations()

        # 2. Query Performance Benchmarks
        self.benchmark_query_performance()

        # 3. Batch Operations
        self.benchmark_batch_operations()

        # 4. Memory Usage
        self.benchmark_memory_usage()

        return self.results

    def benchmark_duckdb_operations(self):
        """Benchmark basic DuckDB operations."""
        print("1. DuckDB Basic Operations")
        print("-" * 80)

        store = DuckDBStore(db_path=":memory:")

        # Test 1: Insert performance
        print(f"  Testing insert performance ({self.num_records} records)...")
        interactions = self._generate_test_interactions(self.num_records)

        start_time = time.time()
        success_count = 0
        for interaction in interactions:
            if store.insert_interaction(interaction):
                success_count += 1
        insert_time = time.time() - start_time

        insert_rate = self.num_records / insert_time if insert_time > 0 else 0

        self.results['duckdb_insert'] = {
            'total_records': self.num_records,
            'total_time_seconds': insert_time,
            'records_per_second': insert_rate,
            'avg_time_per_record_ms': (insert_time / self.num_records) * 1000,
            'success_rate': success_count / self.num_records
        }

        print(f"    ✓ Inserted {self.num_records} records in {insert_time:.2f}s")
        print(f"    ✓ Rate: {insert_rate:.0f} records/second")
        print(f"    ✓ Avg: {(insert_time / self.num_records) * 1000:.2f}ms per record")
        print()

        # Test 2: Simple query performance
        print(f"  Testing simple queries...")
        query_times = []
        for _ in range(min(50, self.num_queries)):
            start = time.time()
            _ = store.get_cost_by_day(days=30)
            query_times.append((time.time() - start) * 1000)

        self.results['duckdb_simple_query'] = {
            'num_queries': len(query_times),
            'avg_time_ms': sum(query_times) / len(query_times),
            'min_time_ms': min(query_times),
            'max_time_ms': max(query_times),
            'p50_ms': sorted(query_times)[len(query_times) // 2],
            'p95_ms': sorted(query_times)[int(len(query_times) * 0.95)],
            'p99_ms': sorted(query_times)[int(len(query_times) * 0.99)],
        }

        print(f"    ✓ Ran {len(query_times)} queries")
        print(f"    ✓ Avg: {self.results['duckdb_simple_query']['avg_time_ms']:.2f}ms")
        print(f"    ✓ P50: {self.results['duckdb_simple_query']['p50_ms']:.2f}ms")
        print(f"    ✓ P95: {self.results['duckdb_simple_query']['p95_ms']:.2f}ms")
        print(f"    ✓ P99: {self.results['duckdb_simple_query']['p99_ms']:.2f}ms")
        print()

        store.close()

    def benchmark_query_performance(self):
        """Benchmark different query types."""
        print("2. Query Performance by Type")
        print("-" * 80)

        store = DuckDBStore(db_path=":memory:")

        # Insert test data
        interactions = self._generate_test_interactions(self.num_records)
        for interaction in interactions:
            store.insert_interaction(interaction)

        query_types = {
            'get_cost_by_day': lambda: store.get_cost_by_day(days=30),
            'get_cost_by_model': lambda: store.get_cost_by_model(days=30),
            'get_token_stats': lambda: store.get_token_stats(days=30),
            'get_top_users_by_cost': lambda: store.get_top_users_by_cost(days=30, limit=10),
        }

        for query_name, query_func in query_types.items():
            print(f"  Testing {query_name}...")
            times = []
            num_runs = min(30, self.num_queries // 4)

            for _ in range(num_runs):
                start = time.time()
                _ = query_func()
                times.append((time.time() - start) * 1000)

            self.results[f'query_{query_name}'] = {
                'avg_time_ms': sum(times) / len(times),
                'min_time_ms': min(times),
                'max_time_ms': max(times),
                'p95_ms': sorted(times)[int(len(times) * 0.95)],
            }

            print(f"    ✓ Avg: {self.results[f'query_{query_name}']['avg_time_ms']:.2f}ms")
            print(f"    ✓ P95: {self.results[f'query_{query_name}']['p95_ms']:.2f}ms")

        print()
        store.close()

    def benchmark_batch_operations(self):
        """Benchmark batch insert operations."""
        print("3. Batch Operations")
        print("-" * 80)

        store = DuckDBStore(db_path=":memory:")

        batch_sizes = [1, 10, 50, 100] if not self.quick else [1, 10, 50]

        for batch_size in batch_sizes:
            print(f"  Testing batch size: {batch_size}")
            interactions = self._generate_test_interactions(batch_size)

            start_time = time.time()
            for interaction in interactions:
                store.insert_interaction(interaction)
            batch_time = time.time() - start_time

            rate = batch_size / batch_time if batch_time > 0 else 0

            self.results[f'batch_insert_{batch_size}'] = {
                'batch_size': batch_size,
                'total_time_seconds': batch_time,
                'records_per_second': rate,
                'avg_time_per_record_ms': (batch_time / batch_size) * 1000,
            }

            print(f"    ✓ Time: {batch_time:.3f}s")
            print(f"    ✓ Rate: {rate:.0f} records/second")

        print()
        store.close()

    def benchmark_memory_usage(self):
        """Benchmark memory usage (simplified)."""
        print("4. Memory Usage")
        print("-" * 80)

        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())

            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Create store and insert data
            store = DuckDBStore(db_path=":memory:")
            interactions = self._generate_test_interactions(self.num_records)
            for interaction in interactions:
                store.insert_interaction(interaction)

            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_used = mem_after - mem_before

            self.results['memory_usage'] = {
                'before_mb': mem_before,
                'after_mb': mem_after,
                'used_mb': mem_used,
                'per_record_kb': (mem_used * 1024) / self.num_records,
            }

            print(f"  ✓ Memory before: {mem_before:.2f} MB")
            print(f"  ✓ Memory after: {mem_after:.2f} MB")
            print(f"  ✓ Memory used: {mem_used:.2f} MB")
            print(f"  ✓ Per record: {(mem_used * 1024) / self.num_records:.2f} KB")

            store.close()

        except ImportError:
            print("  ⚠ psutil not installed, skipping memory benchmarks")
            self.results['memory_usage'] = {'status': 'skipped', 'reason': 'psutil not installed'}

        print()

    def _generate_test_interactions(self, count: int) -> List[LLMInteraction]:
        """Generate test interactions for benchmarking."""
        interactions = []
        base_time = datetime.now()

        models = ["gpt-4", "gpt-3.5-turbo", "claude-2", "claude-instant"]
        users = [f"user_{i}" for i in range(10)]

        for i in range(count):
            interaction = LLMInteraction(
                interaction_id=f"bench_{i}_{int(time.time() * 1000000)}",
                user_id=users[i % len(users)],
                model=models[i % len(models)],
                provider=ModelProvider.OPENAI if i % 2 == 0 else ModelProvider.ANTHROPIC,
                prompt=f"Test prompt {i}" * 10,  # Make it realistic size
                response=f"Test response {i}" * 20,
                input_tokens=100 + (i % 200),
                output_tokens=150 + (i % 300),
                latency_ms=50.0 + (i % 500),
                cost_usd=0.001 + (i % 10) * 0.0001,
                timestamp=base_time - timedelta(hours=i % 720),  # 30 days spread
            )
            interactions.append(interaction)

        return interactions

    def print_summary(self):
        """Print benchmark summary."""
        print()
        print("=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)
        print()

        # DuckDB Performance
        if 'duckdb_insert' in self.results:
            print("DuckDB Insert Performance:")
            print(f"  • {self.results['duckdb_insert']['records_per_second']:.0f} records/second")
            print(f"  • {self.results['duckdb_insert']['avg_time_per_record_ms']:.2f}ms per record")
            print()

        # Query Performance
        print("Query Performance (P95 latency):")
        for key, value in self.results.items():
            if key.startswith('query_'):
                query_name = key.replace('query_', '')
                print(f"  • {query_name:30s}: {value['p95_ms']:6.2f}ms")
        print()

        # Memory
        if 'memory_usage' in self.results and 'used_mb' in self.results['memory_usage']:
            print("Memory Usage:")
            print(f"  • Total: {self.results['memory_usage']['used_mb']:.2f} MB")
            print(f"  • Per Record: {self.results['memory_usage']['per_record_kb']:.2f} KB")
            print()

    def save_results(self, filename: str = "benchmark_results.json"):
        """Save results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"✓ Results saved to {filename}")

    def visualize_results(self):
        """Create visualizations of benchmark results."""
        if not HAS_MATPLOTLIB:
            print("⚠ Matplotlib not installed. Cannot create visualizations.")
            return

        print("Creating visualizations...")

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('LLM Feature Store Performance Benchmarks', fontsize=16, fontweight='bold')

        # 1. Query Performance Comparison
        ax = axes[0, 0]
        query_names = []
        query_times = []
        for key, value in self.results.items():
            if key.startswith('query_'):
                query_names.append(key.replace('query_', '').replace('_', '\n'))
                query_times.append(value['avg_time_ms'])

        if query_names:
            bars = ax.bar(query_names, query_times, color='steelblue', alpha=0.7)
            ax.set_ylabel('Average Time (ms)', fontweight='bold')
            ax.set_title('Query Performance by Type')
            ax.tick_params(axis='x', rotation=0)
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}ms',
                       ha='center', va='bottom', fontsize=9)

        # 2. Batch Insert Performance
        ax = axes[0, 1]
        batch_sizes = []
        batch_rates = []
        for key, value in self.results.items():
            if key.startswith('batch_insert_'):
                batch_sizes.append(value['batch_size'])
                batch_rates.append(value['records_per_second'])

        if batch_sizes:
            ax.plot(batch_sizes, batch_rates, marker='o', linewidth=2,
                   markersize=8, color='green', alpha=0.7)
            ax.set_xlabel('Batch Size', fontweight='bold')
            ax.set_ylabel('Records/Second', fontweight='bold')
            ax.set_title('Batch Insert Throughput')
            ax.grid(True, alpha=0.3)
            for x, y in zip(batch_sizes, batch_rates):
                ax.annotate(f'{y:.0f}', (x, y), textcoords="offset points",
                           xytext=(0,10), ha='center', fontsize=9)

        # 3. Query Latency Distribution
        ax = axes[1, 0]
        if 'duckdb_simple_query' in self.results:
            metrics = self.results['duckdb_simple_query']
            percentiles = ['min', 'p50', 'p95', 'p99', 'max']
            values = [metrics[f'{p}_time_ms'] if p in ['min', 'max'] else metrics[f'{p}_ms']
                     for p in percentiles]

            bars = ax.bar(percentiles, values, color=['green', 'yellow', 'orange', 'red', 'darkred'],
                         alpha=0.7)
            ax.set_ylabel('Latency (ms)', fontweight='bold')
            ax.set_title('Query Latency Distribution')
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom', fontsize=9)

        # 4. Performance Summary Table
        ax = axes[1, 1]
        ax.axis('off')

        summary_data = []
        if 'duckdb_insert' in self.results:
            summary_data.append(['Insert Rate', f"{self.results['duckdb_insert']['records_per_second']:.0f} rec/s"])
            summary_data.append(['Insert Latency', f"{self.results['duckdb_insert']['avg_time_per_record_ms']:.2f}ms"])

        if 'duckdb_simple_query' in self.results:
            summary_data.append(['Query P95', f"{self.results['duckdb_simple_query']['p95_ms']:.2f}ms"])

        if 'memory_usage' in self.results and 'used_mb' in self.results['memory_usage']:
            summary_data.append(['Memory Used', f"{self.results['memory_usage']['used_mb']:.2f}MB"])
            summary_data.append(['Memory/Record', f"{self.results['memory_usage']['per_record_kb']:.2f}KB"])

        if summary_data:
            table = ax.table(cellText=summary_data,
                           colLabels=['Metric', 'Value'],
                           cellLoc='left',
                           loc='center',
                           colWidths=[0.6, 0.4])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2)
            ax.set_title('Performance Summary')

        plt.tight_layout()
        filename = 'benchmark_results.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"✓ Visualization saved to {filename}")

        plt.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Performance Benchmarking for LLM Feature Store')
    parser.add_argument('--quick', action='store_true', help='Run quick benchmarks')
    parser.add_argument('--detailed', action='store_true', help='Run detailed benchmarks')
    parser.add_argument('--visualize', action='store_true', help='Generate visualizations')
    parser.add_argument('--output', type=str, default='benchmark_results.json',
                       help='Output file for results')

    args = parser.parse_args()

    # Determine benchmark mode
    quick = args.quick or (not args.detailed)

    # Run benchmarks
    benchmark = PerformanceBenchmark(quick=quick)
    results = benchmark.run_all()

    # Print summary
    benchmark.print_summary()

    # Save results
    benchmark.save_results(args.output)

    # Generate visualizations
    if args.visualize or not args.quick:
        benchmark.visualize_results()

    print()
    print("=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
