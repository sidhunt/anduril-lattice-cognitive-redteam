import pytest
from lattice_cognitive.engine.maslow import MaslowLevel, MotivationProfile


def test_maslow_levels_completeness():
    expected_tiers = {"SURVIVAL", "SECURITY", "BELONGING", "ESTEEM", "SELF_ACTUALIZATION"}
    actual_tiers = {tier.value for tier in MaslowLevel}
    assert actual_tiers == expected_tiers


def test_motivation_profile_normalization():
    profile = MotivationProfile(
        base_weights={
            MaslowLevel.SURVIVAL: 10.0,
            MaslowLevel.SECURITY: 10.0,
            MaslowLevel.BELONGING: 10.0,
            MaslowLevel.ESTEEM: 10.0,
            MaslowLevel.SELF_ACTUALIZATION: 10.0,
        }
    )
    profile.normalize()
    total = sum(profile.base_weights.values())
    assert pytest.approx(total, 0.001) == 1.0
    for w in profile.base_weights.values():
        assert pytest.approx(w, 0.001) == 0.20


def test_dynamic_weights_kinetic_threat_spike():
    profile = MotivationProfile()
    weights_normal = profile.compute_active_weights(
        threat_proximity=0.1,
        lattice_task_intensity=0.2,
        swarm_health_ratio=1.0,
    )
    weights_crisis = profile.compute_active_weights(
        threat_proximity=0.9,
        lattice_task_intensity=0.2,
        swarm_health_ratio=1.0,
    )

    # In crisis, Survival (Tier 1) should dominate
    assert weights_crisis[MaslowLevel.SURVIVAL] > weights_normal[MaslowLevel.SURVIVAL]
    assert pytest.approx(sum(weights_crisis.values()), 0.01) == 1.0
