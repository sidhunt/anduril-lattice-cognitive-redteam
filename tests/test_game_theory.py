"""
Tests for Game-Theoretic Stackelberg & Bayesian Signaling Formulations.
Validates operator hesitation under bounded rationality, Hick-Hyman latency,
and Cognitive Resilience Architecture (CRA) swarm clustering mitigations.
"""

import math
import pytest
from lattice_cognitive.game_theory.stackelberg import (
    StackelbergGameEngine,
    AdversaryStrategy,
    OperatorPayoffProfile,
    EquilibriumResult,
)
from lattice_cognitive.game_theory.signaling import (
    BayesianSignalingGame,
    SignalType,
    ThreatType,
    SignalingEquilibrium,
)


def test_adversary_strategy_normalization():
    strat = AdversaryStrategy(p_kinetic=1.0, p_feint=2.0, p_terrain_masked=1.0, total_tracks=20)
    assert abs(strat.p_kinetic - 0.25) < 1e-4
    assert abs(strat.p_feint - 0.50) < 1e-4
    assert abs(strat.p_terrain_masked - 0.25) < 1e-4

    with pytest.raises(ValueError):
        AdversaryStrategy(p_kinetic=0.0, p_feint=0.0, p_terrain_masked=0.0)


def test_hick_hyman_latency_and_corridor():
    engine = StackelbergGameEngine()
    profile = engine.profile

    # Latency increases with number of tracks
    lat_10 = engine.compute_hick_hyman_latency(num_tracks=10, ambiguity=0.20)
    lat_30 = engine.compute_hick_hyman_latency(num_tracks=30, ambiguity=0.20)
    assert lat_30 > lat_10

    # Ambiguity penalty peaks inside [0.40, 0.60] indecision corridor
    lat_corridor = engine.compute_hick_hyman_latency(num_tracks=30, ambiguity=0.50)
    lat_outside = engine.compute_hick_hyman_latency(num_tracks=30, ambiguity=0.10)
    assert lat_corridor > lat_outside * 1.5


def test_stackelberg_subgame_perfect_equilibrium():
    engine = StackelbergGameEngine()
    eq = engine.solve_equilibrium(adversary_budget_tracks=30, cluster_mitigation=False)

    assert isinstance(eq, EquilibriumResult)
    assert eq.in_indecision_corridor is True
    assert 0.40 <= eq.operator_posterior_ambiguity <= 0.60
    # p95 reaction latency should reflect ~12.6s corridor delay
    assert 11.0 <= eq.p95_reaction_latency_s <= 14.5
    # Airspace penetration at Mach 0.85 (289.25 m/s) over ~12.6s should be ~3.65 km
    assert 3.2 <= eq.penetration_gap_km <= 4.2
    assert eq.adversary_payoff > 0.0


def test_swarm_clustering_mitigation_impact():
    engine = StackelbergGameEngine()
    impact = engine.evaluate_swarm_clustering_impact(adversary_budget_tracks=30)

    assert "unmitigated" in impact
    assert "mitigated_cra_clustering" in impact
    assert impact["hesitation_reduction_pct"] > 40.0
    assert impact["airspace_saved_km"] > 1.5
    # Mitigated latency is substantially lower than unmitigated
    assert impact["mitigated_cra_clustering"]["p95_latency_s"] < impact["unmitigated"]["p95_latency_s"]


def test_bayesian_signaling_game_priors_and_bayes_update():
    game = BayesianSignalingGame(prior_kinetic=0.20, prior_feint=0.60, prior_masked=0.20)
    assert abs(sum(game.priors.values()) - 1.0) < 1e-4

    # High-G signal Bayes update
    post = game.update_posterior_belief(SignalType.COSTLY_HIGH_G)
    assert abs(sum(post.values()) - 1.0) < 1e-4
    # Cheap talk feint should have low kinetic posterior
    post_feint = game.update_posterior_belief(SignalType.CHEAP_TALK_FEINT)
    assert post_feint[ThreatType.KINETIC_STRIKE] < post[ThreatType.KINETIC_STRIKE]


def test_signaling_equilibrium_pooling_and_mitigation():
    game = BayesianSignalingGame()

    # Unmitigated state produces pooling in [0.4, 0.6] corridor for high-G feints
    unmitigated = game.evaluate_equilibrium(cluster_compressed=False)
    assert unmitigated.pooling_in_corridor is True
    assert unmitigated.equilibrium_type == "POOLING"
    assert unmitigated.operator_actions[SignalType.COSTLY_HIGH_G] == "HESITATE_DELIBERATE"

    # Multi-sensor cluster compression breaks pooling into separating equilibrium
    mitigated = game.evaluate_equilibrium(cluster_compressed=True)
    assert mitigated.equilibrium_type == "SEPARATING"
    assert mitigated.operator_actions[SignalType.COSTLY_HIGH_G] == "INTERCEPT_IMMEDIATE"
    assert mitigated.operator_actions[SignalType.CHEAP_TALK_FEINT] == "IGNORE_OR_STANDBY"
