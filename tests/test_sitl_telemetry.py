import pytest
from lattice_cognitive.sim.sitl_adapter import SitlAdapter, VirtualSwarmScenario
from lattice_cognitive.twin.mock_sdk import MockLatticeTwin
from lattice_cognitive.twin.schema import TrackEntity, Classification
from lattice_cognitive.analytics.hesitation_predictor import OperatorHesitationPredictor, SaturationLevel
from lattice_cognitive.analytics.mitigation import CognitiveResilienceLayer


def test_sitl_telemetry_generation_and_parsing():
    adapter = SitlAdapter(origin_lat=33.5, origin_lon=-116.5)
    scenario = VirtualSwarmScenario(num_drones=12, feint_radius_m=2500.0)

    # 1. Generate virtual MAVLink telemetry
    stream_bytes = adapter.generate_virtual_swarm_telemetry(scenario, elapsed_s=2.0)
    assert len(stream_bytes) > 0

    # 2. Parse stream into Lattice COP TrackEntities
    tracks = adapter.parse_mavlink_stream(stream_bytes)
    assert len(tracks) == 12

    for track in tracks:
        assert track.entity_id.startswith("SITL-UAV-")
        assert track.classification in [Classification.UNKNOWN, Classification.DECOY]
        assert track.speed_mps > 0.0
        assert 33.0 <= track.latitude <= 34.0
        assert -117.0 <= track.longitude <= -116.0


def test_sitl_twin_injection_and_hesitation_loop():
    twin = MockLatticeTwin()
    adapter = SitlAdapter(origin_lat=33.5, origin_lon=-116.5)
    predictor = OperatorHesitationPredictor(base_reaction_ms=1800.0, working_memory_capacity=7)

    # 1. Baseline calm state
    calm_metrics = predictor.compute_hesitation_index(
        active_tracks_count=len(twin.tracks),
        classification_ambiguity=0.1,
        maslow_state_oscillation_rate=0.0,
        concurrent_pending_tasks=0,
    )
    assert calm_metrics["saturation_level"] == SaturationLevel.NOMINAL.value
    assert calm_metrics["decision_hesitation_index"] < 0.35

    # 2. Inject virtual 24-drone swarm feint
    scenario = VirtualSwarmScenario(num_drones=24, feint_radius_m=3000.0)
    injected_tracks = adapter.inject_swarm_into_twin(twin, scenario, elapsed_s=5.0)
    assert len(injected_tracks) == 24
    assert len(twin.tracks) == 24 + 2

    # Mark some tracks as high-ambiguity decoys
    for i, track in enumerate(twin.tracks.values()):
        if i % 3 == 0:
            track.classification = Classification.DECOY
            track.rcs_sqm = 0.04

    # 3. Evaluate saturation under virtual SITL swarm
    swarm_metrics = predictor.compute_hesitation_index(
        active_tracks_count=len(twin.tracks),
        classification_ambiguity=0.85,
        maslow_state_oscillation_rate=0.75,
        concurrent_pending_tasks=6,
    )
    assert swarm_metrics["saturation_level"] == SaturationLevel.COGNITIVE_BOTTLENECK.value
    assert swarm_metrics["decision_hesitation_index"] >= 0.70
    assert swarm_metrics["predicted_reaction_time_ms"] > 6000.0

    # 4. Apply Cognitive Resilience Layer (CRA) mitigation
    triage_result = CognitiveResilienceLayer.triage_tracks_for_operator(
        list(twin.tracks.values()),
        hesitation_index=swarm_metrics["decision_hesitation_index"],
    )
    assert triage_result["clustered_decoy_count"] > 0
    assert triage_result["effective_chunks_presented"] < len(twin.tracks)
    assert triage_result["projected_latency_reduction_pct"] > 30.0
