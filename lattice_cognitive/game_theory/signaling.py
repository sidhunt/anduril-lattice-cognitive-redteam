"""
Bayesian Signaling Game Formulation of C2 Threat Verification.
Models asymmetric information where adversary chooses costly signals (kinetic weapons)
or cheap-talk signals (electronic feints/decoys) to manipulate operator posterior belief.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ThreatType(str, Enum):
    KINETIC_STRIKE = "kinetic_strike"       # Real munition / warhead (high cost to adversary)
    ELECTRONIC_FEINT = "electronic_feint"   # Low-cost radar decoy / drone mimicking signature
    TERRAIN_MASKED = "terrain_masked"       # Low-observable ingress along terrain contours


class SignalType(str, Enum):
    COSTLY_HIGH_G = "costly_high_g"         # High-G evasive maneuver with afterburner thermal signature
    CHEAP_TALK_FEINT = "cheap_talk_feint"   # Synthetic radar return or mini-jammer pulse
    RADAR_SHADOW = "radar_shadow"           # Intermittent Doppler signature from ridgeline masking


@dataclass
class SignalingEquilibrium:
    """Outcome of Bayesian signaling analysis."""
    equilibrium_type: str                  # "POOLING" or "SEPARATING" or "SEMI_SEPARATING"
    prior_threat_prob: float
    posterior_beliefs: Dict[SignalType, float] # P(Kinetic | Signal)
    operator_actions: Dict[SignalType, str]    # "INTERCEPT", "HESITATE_DELIBERATE", "IGNORE"
    expected_adversary_utility: float
    expected_operator_utility: float
    entropy_bits: float
    pooling_in_corridor: bool


class BayesianSignalingGame:
    """
    Simulates Bayesian Signaling Game with asymmetric information.
    Nature assigns ThreatType theta with prior P(theta).
    Adversary sends SignalType s.
    Lattice Operator updates belief mu(theta | s) and decides whether to authorize immediate interception.
    """

    def __init__(
        self,
        prior_kinetic: float = 0.35,
        prior_feint: float = 0.50,
        prior_masked: float = 0.15,
    ):
        total = prior_kinetic + prior_feint + prior_masked
        self.priors: Dict[ThreatType, float] = {
            ThreatType.KINETIC_STRIKE: prior_kinetic / total,
            ThreatType.ELECTRONIC_FEINT: prior_feint / total,
            ThreatType.TERRAIN_MASKED: prior_masked / total,
        }

        # Signal transmission probabilities P(Signal | ThreatType)
        # Adversary tunes decoy RCS to mimic kinetic signatures (pooling)
        self.signal_likelihoods: Dict[ThreatType, Dict[SignalType, float]] = {
            ThreatType.KINETIC_STRIKE: {
                SignalType.COSTLY_HIGH_G: 0.70,
                SignalType.CHEAP_TALK_FEINT: 0.15,
                SignalType.RADAR_SHADOW: 0.15,
            },
            ThreatType.ELECTRONIC_FEINT: {
                # Decoy aggressively mimics high-G signature to trigger false alarms or hesitation
                SignalType.COSTLY_HIGH_G: 0.45,
                SignalType.CHEAP_TALK_FEINT: 0.45,
                SignalType.RADAR_SHADOW: 0.10,
            },
            ThreatType.TERRAIN_MASKED: {
                SignalType.COSTLY_HIGH_G: 0.10,
                SignalType.CHEAP_TALK_FEINT: 0.20,
                SignalType.RADAR_SHADOW: 0.70,
            },
        }

    def compute_marginal_signal_probability(self, signal: SignalType) -> float:
        """P(Signal) = sum_theta P(Signal | theta) * P(theta)."""
        return sum(
            self.signal_likelihoods[th][signal] * self.priors[th]
            for th in ThreatType
        )

    def update_posterior_belief(self, signal: SignalType) -> Dict[ThreatType, float]:
        """
        Bayes' Rule:
        P(theta | s) = (P(s | theta) * P(theta)) / P(s)
        """
        p_s = self.compute_marginal_signal_probability(signal)
        if p_s <= 1e-9:
            return {th: self.priors[th] for th in ThreatType}

        posteriors = {}
        for th in ThreatType:
            p_s_given_th = self.signal_likelihoods[th][signal]
            posteriors[th] = (p_s_given_th * self.priors[th]) / p_s
        return posteriors

    def compute_signal_entropy(self, signal: SignalType) -> float:
        """Shannon entropy H(theta | s) = -sum P(theta | s) * log2(P(theta | s))."""
        post = self.update_posterior_belief(signal)
        ent = 0.0
        for p in post.values():
            if p > 1e-9:
                ent -= p * math.log2(p)
        return ent

    def evaluate_equilibrium(self, cluster_compressed: bool = False) -> SignalingEquilibrium:
        """
        Computes Perfect Bayesian Equilibrium (PBE).
        When cluster_compressed=True, multi-sensor clustering separates feints from real threats.
        """
        if cluster_compressed:
            # Multi-spectral fusion separates decoys from real engines
            self.signal_likelihoods[ThreatType.ELECTRONIC_FEINT][SignalType.COSTLY_HIGH_G] = 0.05
            self.signal_likelihoods[ThreatType.ELECTRONIC_FEINT][SignalType.CHEAP_TALK_FEINT] = 0.85
            self.signal_likelihoods[ThreatType.KINETIC_STRIKE][SignalType.COSTLY_HIGH_G] = 0.88

        posterior_kinetic = {}
        actions = {}
        total_entropy = 0.0

        for sig in SignalType:
            post = self.update_posterior_belief(sig)
            mu_kinetic = post[ThreatType.KINETIC_STRIKE]
            posterior_kinetic[sig] = round(mu_kinetic, 3)

            # Operator best response:
            # If mu > 0.60: immediate authorization
            # If 0.40 <= mu <= 0.60: indecision corridor (hesitation)
            # If mu < 0.40: ignore / low-priority monitor
            if mu_kinetic > 0.60:
                actions[sig] = "INTERCEPT_IMMEDIATE"
            elif 0.40 <= mu_kinetic <= 0.60:
                actions[sig] = "HESITATE_DELIBERATE"
            else:
                actions[sig] = "IGNORE_OR_STANDBY"

            total_entropy += self.compute_signal_entropy(sig) * self.compute_marginal_signal_probability(sig)

        # Check for pooling: if COSTLY_HIGH_G has posterior in [0.4, 0.6]
        high_g_mu = posterior_kinetic[SignalType.COSTLY_HIGH_G]
        in_corridor = (0.40 <= high_g_mu <= 0.60)
        eq_type = "POOLING" if in_corridor else "SEPARATING"

        adv_utility = 12.6 * high_g_mu if in_corridor else 4.2
        op_utility = -18.5 if in_corridor else -4.1

        return SignalingEquilibrium(
            equilibrium_type=eq_type,
            prior_threat_prob=round(self.priors[ThreatType.KINETIC_STRIKE], 3),
            posterior_beliefs=posterior_kinetic,
            operator_actions=actions,
            expected_adversary_utility=round(adv_utility, 2),
            expected_operator_utility=round(op_utility, 2),
            entropy_bits=round(total_entropy, 3),
            pooling_in_corridor=in_corridor,
        )
