import pytest
from lattice_cognitive.analytics.physiological_validator import (
    EmpiricalWorkloadCalibrator,
    DatasetSource,
    PhysiologicalSample,
)
from lattice_cognitive.analytics.hesitation_predictor import OperatorHesitationPredictor, SaturationLevel


def test_hf_metadata_query():
    calibrator = EmpiricalWorkloadCalibrator()
    # Test all 3 datasets
    for ds in [
        DatasetSource.STEW_MULTITASKING,
        DatasetSource.DS003838_PUPILLOMETRY,
        DatasetSource.DS007169_NBACK_4TIER,
    ]:
        meta = calibrator.fetch_hf_metadata(ds)
        assert meta["id"] == ds.value


def test_stew_multitasking_calibration():
    calibrator = EmpiricalWorkloadCalibrator()

    # 1. Low workload calibration
    low_sample = calibrator.generate_calibrated_synthetic_sample(
        DatasetSource.STEW_MULTITASKING, workload_level=0.1
    )
    assert low_sample.dataset == DatasetSource.STEW_MULTITASKING
    assert low_sample.cognitive_load_score == 0.1
    assert low_sample.reaction_latency_ms < 2500.0
    assert low_sample.spectral_theta_alpha_ratio is not None
    assert low_sample.spectral_theta_alpha_ratio < 1.2

    # 2. Saturated workload calibration
    sat_sample = calibrator.generate_calibrated_synthetic_sample(
        DatasetSource.STEW_MULTITASKING, workload_level=0.85
    )
    assert sat_sample.reaction_latency_ms > 5000.0
    assert sat_sample.spectral_theta_alpha_ratio > 1.8


def test_ds003838_pupillometry_calibration():
    calibrator = EmpiricalWorkloadCalibrator()

    # 1. Baseline resting state
    calm = calibrator.generate_calibrated_synthetic_sample(
        DatasetSource.DS003838_PUPILLOMETRY, workload_level=0.05
    )
    assert calm.pupil_dilation_mm is not None
    assert 3.20 <= calm.pupil_dilation_mm <= 3.35

    # 2. Saturated state (+40% dilation)
    saturated = calibrator.generate_calibrated_synthetic_sample(
        DatasetSource.DS003838_PUPILLOMETRY, workload_level=0.90
    )
    assert saturated.pupil_dilation_mm > 4.40
    assert saturated.reaction_latency_ms > 4500.0


def test_ds007169_nback_4tier_calibration():
    calibrator = EmpiricalWorkloadCalibrator()

    # Test all 4 discrete tiers
    t0 = calibrator.generate_calibrated_synthetic_sample(
        DatasetSource.DS007169_NBACK_4TIER, workload_level=0.0
    )
    assert t0.task_tier == 0
    assert t0.reaction_latency_ms == 1420.0

    t3 = calibrator.generate_calibrated_synthetic_sample(
        DatasetSource.DS007169_NBACK_4TIER, workload_level=1.0
    )
    assert t3.task_tier == 3
    assert t3.reaction_latency_ms == 8120.0


def test_dhi_validation_across_all_3_benchmarks():
    calibrator = EmpiricalWorkloadCalibrator()
    predictor = OperatorHesitationPredictor(base_reaction_ms=1800.0)

    # Calculate model DHI under high multi-task saturation
    dhi_result = predictor.compute_hesitation_index(
        active_tracks_count=18,
        classification_ambiguity=0.85,
        maslow_state_oscillation_rate=0.70,
        concurrent_pending_tasks=5,
    )
    dhi = dhi_result["decision_hesitation_index"]
    assert dhi >= 0.70

    # Validate against STEW
    v_stew = calibrator.validate_dhi_against_hf_benchmark(dhi, DatasetSource.STEW_MULTITASKING)
    assert v_stew["cognitive_saturation_exceeded"]
    assert v_stew["neurophysiological_verdict"] == "CRITICAL_SATURATION"
    assert v_stew["empirical_fit_error_pct"] < 5.0

    # Validate against ds003838 Pupillometry
    v_pupil = calibrator.validate_dhi_against_hf_benchmark(dhi, DatasetSource.DS003838_PUPILLOMETRY)
    assert v_pupil["pupil_dilation_mm"] > 4.10
    assert v_pupil["cognitive_saturation_exceeded"]

    # Validate against ds007169 4-Tier
    v_tier = calibrator.validate_dhi_against_hf_benchmark(dhi, DatasetSource.DS007169_NBACK_4TIER)
    assert v_tier["calibrated_latency_ms"] >= 4850.0
