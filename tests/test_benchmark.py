import pytest
from lattice_cognitive.analytics.benchmark import MonteCarloHesitationBenchmark


def test_monte_carlo_statistical_properties():
    bench = MonteCarloHesitationBenchmark(n_trials=200, seed=123)
    results = bench.run_benchmark()

    assert results["n_trials"] == 200
    assert results["baseline_ort_mean_ms"] > results["mitigated_ort_mean_ms"]
    assert results["mean_reaction_time_reduction_pct"] > 30.0
    assert results["mean_penetration_corridor_prevented_m"] > 300.0
    assert results["baseline_ort_p95_ms"] > results["mitigated_ort_p95_ms"]
