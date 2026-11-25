import pytest
from lattice_cognitive.analytics.hesitation_predictor import OperatorHesitationPredictor, SaturationLevel
from lattice_cognitive.analytics.mitigation import CognitiveResilienceLayer
from lattice_cognitive.twin.schema import TrackEntity, Classification


def test_hesitation_index_scaling():
    predictor = OperatorHesitationPredictor(base_reaction_ms=2000.0)

    # Calm state
    calm = predictor.compute_hesitation_index(
        active_tracks_count=2,
        classification_ambiguity=0.1,
        maslow_state_oscillation_rate=0.0,
        concurrent_pending_tasks=1,
    )
    assert calm["saturation_level"] == SaturationLevel.NOMINAL.value
    assert calm["decision_hesitation_index"] < 0.35
    assert calm["predicted_reaction_time_ms"] < 3500.0

    # Overload / Deceptive state
    overload = predictor.compute_hesitation_index(
        active_tracks_count=18,
        classification_ambiguity=0.9,
        maslow_state_oscillation_rate=0.8,
        concurrent_pending_tasks=5,
    )
    assert overload["saturation_level"] == SaturationLevel.COGNITIVE_BOTTLENECK.value
    assert overload["decision_hesitation_index"] >= 0.70
    assert overload["predicted_reaction_time_ms"] > 6000.0


def test_cognitive_resilience_layer_triage():
    tracks = [
        TrackEntity(
            entity_id="hostile-01",
            callsign="HOSTILE-CRUISE",
            classification=Classification.HOSTILE,
            latitude=34.0,
            longitude=-118.0,
            altitude_m=500.0,
            speed_mps=350.0,
            heading_deg=0.0,
        ),
        TrackEntity(
            entity_id="decoy-01",
            callsign="DECOY-DRONE-A",
            classification=Classification.DECOY,
            latitude=34.1,
            longitude=-118.1,
            altitude_m=3000.0,
            speed_mps=80.0,
            heading_deg=45.0,
            rcs_sqm=0.05,
        ),
        TrackEntity(
            entity_id="decoy-02",
            callsign="DECOY-DRONE-B",
            classification=Classification.DECOY,
            latitude=34.2,
            longitude=-118.2,
            altitude_m=3000.0,
            speed_mps=80.0,
            heading_deg=45.0,
            rcs_sqm=0.05,
        ),
    ]

    triage = CognitiveResilienceLayer.triage_tracks_for_operator(
        tracks=tracks,
        hesitation_index=0.75,
    )

    assert triage["clustered_decoy_count"] == 2
    assert "hostile-01" in triage["critical_focus_tracks"]
    assert triage["effective_chunks_presented"] == 2  # 1 hostile + 1 clustered decoy card
    assert triage["resilience_status"] == "ACTIVE_SMOOTHING"
