"""
Stackelberg Formulation of C2 Operator Hesitation.
Adversary Swarm acts as Leader choosing mixed attack vectors (kinetic vs. feints),
while Lattice C2 Operator acts as Follower subject to Hick-Hyman cognitive latency limits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AdversaryStrategy:
    """Mixed strategy allocation for the attacking swarm."""
    p_kinetic: float          # Proportion of real kinetic assets (costly signal)
    p_feint: float            # Proportion of high-g cheap-talk radar feints
    p_terrain_masked: float   # Proportion of terrain-masked low-observable tracks
    total_tracks: int = 30    # Total simultaneous tracks injected into airspace

    def __post_init__(self) -> None:
        total = self.p_kinetic + self.p_feint + self.p_terrain_masked
        if total <= 0.0:
            raise ValueError("Strategy probabilities must sum to > 0")
        self.p_kinetic /= total
        self.p_feint /= total
        self.p_terrain_masked /= total


@dataclass
class OperatorPayoffProfile:
    """Cognitive and operational parameters of the defense operator."""
    baseline_latency_s: float = 1.60          # Minimal motor response time (s)
    hick_hyman_rate_s: float = 0.85           # Latency per bit of entropy (s/bit)
    miss_penalty: float = 100.0               # Cost of allowing real strike to penetrate
    false_alarm_penalty: float = 15.0         # Cost of expending interceptor on feint
    indecision_band_lower: float = 0.40       # Ambiguity threshold lower bound
    indecision_band_upper: float = 0.60       # Ambiguity threshold upper bound
    mach_speed: float = 0.85                  # Threat velocity relative to speed of sound
    speed_of_sound_mps: float = 340.29        # Airspeed constant (m/s)


@dataclass
class EquilibriumResult:
    """Computed subgame perfect equilibrium outcome."""
    leader_strategy: AdversaryStrategy
    operator_posterior_ambiguity: float
    p95_reaction_latency_s: float
    penetration_gap_km: float
    adversary_payoff: float
    operator_payoff: float
    in_indecision_corridor: bool


class StackelbergGameEngine:
    """
    Solves and simulates the Stackelberg Leader-Follower game between
    Adversary Swarm (Leader) and Human C2 Operator (Follower).
    """

    def __init__(self, profile: Optional[OperatorPayoffProfile] = None):
        self.profile = profile or OperatorPayoffProfile()

    @property
    def threat_velocity_mps(self) -> float:
        """Translates Mach velocity into meters per second."""
        return self.profile.mach_speed * self.profile.speed_of_sound_mps

    def compute_hick_hyman_latency(self, num_tracks: int, ambiguity: float) -> float:
        """
        Computes human reaction latency under Hick-Hyman logarithmic choice complexity:
        T_react = T_0 + b * log2(N + 1) * (1 + ambiguity_penalty).
        When ambiguity is within [0.4, 0.6], hesitation peaks quadratically.
        """
        bits_of_choice = math.log2(max(1, num_tracks) + 1.0)
        base_reaction = self.profile.baseline_latency_s + self.profile.hick_hyman_rate_s * bits_of_choice

        # Ambiguity penalty peaks when belief is at maximum entropy (ambiguity = 0.50)
        # Inside [0.40, 0.60], deliberation overhead scales non-linearly
        dist_from_center = abs(ambiguity - 0.50)
        if self.profile.indecision_band_lower <= ambiguity <= self.profile.indecision_band_upper:
            # High hesitation multiplier in the corridor (peaks at 1.58 when ambiguity = 0.50)
            ambiguity_mult = 1.0 + 0.58 * (1.0 - 10.0 * (dist_from_center ** 2))
        else:
            ambiguity_mult = 1.0 + 0.15 * max(0.0, 1.0 - 2.0 * dist_from_center)

        return base_reaction * ambiguity_mult

    def compute_penetration_gap_meters(self, reaction_time_s: float) -> float:
        """Computes airspace penetration distance during operator deliberation."""
        return self.threat_velocity_mps * reaction_time_s

    def compute_operator_posterior_ambiguity(self, strategy: AdversaryStrategy) -> float:
        """
        Calculates posterior ambiguity under sensor resolution noise.
        Adversary mixed strategy creates ambiguous radar classification profiles.
        """
        # Feints mimic kinetic RCS signatures, pulling belief toward maximum entropy
        # Effective ambiguity is proportional to feint ratio normalized against kinetic tracks
        effective_noise = (strategy.p_feint * 0.92) + (strategy.p_terrain_masked * 0.55)
        ambiguity = min(0.95, max(0.05, 0.50 * effective_noise + 0.50 * (1.0 - abs(strategy.p_kinetic - 0.33))))
        return ambiguity

    def solve_equilibrium(
        self,
        adversary_budget_tracks: int = 30,
        cluster_mitigation: bool = False,
    ) -> EquilibriumResult:
        """
        Finds the Subgame Perfect Equilibrium (SPE).
        Adversary commits to mixed allocation (p_kinetic, p_feint, p_masked)
        to maximize operator latency subject to budget constraints.
        """
        best_adversary_payoff = -float("inf")
        best_strategy = AdversaryStrategy(0.33, 0.34, 0.33, total_tracks=adversary_budget_tracks)
        best_latency = 0.0
        best_ambiguity = 0.50

        # Discretized search over simplex for optimal adversary leader mixed strategy
        step = 0.05
        for pk_i in range(1, 20):
            pk = pk_i * step
            for pf_i in range(1, 20):
                pf = pf_i * step
                if pk + pf >= 1.0:
                    continue
                pt = 1.0 - (pk + pf)

                strat = AdversaryStrategy(pk, pf, pt, total_tracks=adversary_budget_tracks)
                ambiguity = self.compute_operator_posterior_ambiguity(strat)

                effective_tracks = adversary_budget_tracks
                effective_ambiguity = ambiguity
                if cluster_mitigation:
                    # Entropy compression via spatial track clustering reduces choice complexity and resolves ambiguity
                    effective_tracks = max(2, int(round(adversary_budget_tracks * 0.20)))
                    effective_ambiguity = ambiguity * 0.40

                latency = self.compute_hick_hyman_latency(effective_tracks, effective_ambiguity)
                p95_latency = latency * 1.38  # Gumbel/Weibull tail expansion for p95

                # Adversary objective: maximize successful penetration through the hesitation corridor
                # If operator is pinned in [0.4, 0.6] corridor, interceptor dispatch is paralyzed
                in_band = (
                    self.profile.indecision_band_lower <= ambiguity <= self.profile.indecision_band_upper
                )
                penetration_prob = 0.95 if in_band else 0.20
                pen_dist_km = (self.threat_velocity_mps * p95_latency) / 1000.0
                kinetic_cost = pk * adversary_budget_tracks * 0.08
                adv_payoff = (pen_dist_km * penetration_prob) - kinetic_cost

                if adv_payoff > best_adversary_payoff:
                    best_adversary_payoff = adv_payoff
                    best_strategy = strat
                    best_latency = p95_latency
                    best_ambiguity = ambiguity

        pen_gap_km = (self.threat_velocity_mps * best_latency) / 1000.0
        in_corridor = (
            self.profile.indecision_band_lower <= best_ambiguity <= self.profile.indecision_band_upper
        )

        op_payoff = -(self.profile.miss_penalty * (1.0 - math.exp(-best_latency / 10.0)) + self.profile.false_alarm_penalty * best_strategy.p_feint)

        return EquilibriumResult(
            leader_strategy=best_strategy,
            operator_posterior_ambiguity=round(best_ambiguity, 3),
            p95_reaction_latency_s=round(best_latency, 2),
            penetration_gap_km=round(pen_gap_km, 2),
            adversary_payoff=round(best_adversary_payoff, 3),
            operator_payoff=round(op_payoff, 2),
            in_indecision_corridor=in_corridor,
        )

    def evaluate_swarm_clustering_impact(
        self,
        adversary_budget_tracks: int = 30,
    ) -> Dict[str, Any]:
        """
        Evaluates Cognitive Resilience Architecture (CRA) mitigation:
        Entropy compression via track clustering cuts operator choice complexity.
        """
        unmitigated = self.solve_equilibrium(adversary_budget_tracks, cluster_mitigation=False)
        mitigated = self.solve_equilibrium(adversary_budget_tracks, cluster_mitigation=True)

        latency_reduction_pct = (
            (unmitigated.p95_reaction_latency_s - mitigated.p95_reaction_latency_s)
            / unmitigated.p95_reaction_latency_s
            * 100.0
        )
        gap_reduction_km = unmitigated.penetration_gap_km - mitigated.penetration_gap_km

        return {
            "unmitigated": {
                "p95_latency_s": unmitigated.p95_reaction_latency_s,
                "penetration_gap_km": unmitigated.penetration_gap_km,
                "posterior_ambiguity": unmitigated.operator_posterior_ambiguity,
                "in_corridor": unmitigated.in_indecision_corridor,
            },
            "mitigated_cra_clustering": {
                "p95_latency_s": mitigated.p95_reaction_latency_s,
                "penetration_gap_km": mitigated.penetration_gap_km,
                "posterior_ambiguity": mitigated.operator_posterior_ambiguity,
                "in_corridor": mitigated.in_indecision_corridor,
            },
            "hesitation_reduction_pct": round(latency_reduction_pct, 2),
            "airspace_saved_km": round(gap_reduction_km, 2),
        }
