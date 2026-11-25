"""
Operator Hesitation & Cognitive Saturation Analytics.
Models the Human-in-the-Loop (HITL) decision bottleneck in autonomous command & control.
Predicts operator latency, cognitive overload, and vulnerability windows under deceptive maneuvers.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Any
import numpy as np


class SaturationLevel(str, Enum):
    NOMINAL = "NOMINAL"                          # DHI < 0.35 (Operator calm, reaction time 1.5 - 2.5s)
    ELEVATED = "ELEVATED"                        # 0.35 <= DHI < 0.70 (Task-switching latency, 3.0 - 6.0s)
    COGNITIVE_BOTTLENECK = "COGNITIVE_BOTTLENECK"  # DHI >= 0.70 (Severe hesitation, 6.0 - 15.0s, vulnerability window)


class OperatorHesitationPredictor:
    """
    Mathematical model predicting human operator cognitive latency when interfacing
    with autonomous defense operating systems under adversarial deception.
    """

    def __init__(
        self,
        base_reaction_ms: float = 1800.0,
        fatigue_factor: float = 1.0,
        working_memory_capacity: int = 7,  # Miller's Law (7 +/- 2 chunks)
    ):
        self.base_reaction_ms = base_reaction_ms
        self.fatigue_factor = fatigue_factor
        self.capacity = working_memory_capacity

    def compute_hesitation_index(
        self,
        active_tracks_count: int,
        classification_ambiguity: float,
        maslow_state_oscillation_rate: float,
        concurrent_pending_tasks: int,
    ) -> Dict[str, Any]:
        """
        Calculates the Decision Hesitation Index (DHI) and predicts Operator Reaction Time (ORT):

        - active_tracks_count: Total unknown / suspect contacts in airspace
        - classification_ambiguity: 0.0 (certain hostile) to 1.0 (equally likely civilian airliner or decoy)
        - maslow_state_oscillation_rate: frequency of adversary shifting between evasion and aggression
        - concurrent_pending_tasks: queued intercept / track confirmations awaiting human authorization
        """
        # 1. Track density cognitive load (Hick-Hyman Law)
        density_ratio = min(3.0, active_tracks_count / max(1.0, float(self.capacity)))
        density_penalty = np.log2(1.0 + density_ratio) * 0.25

        # 2. Ambiguity penalty (Bayesian uncertainty in Rules of Engagement)
        ambiguity_penalty = (classification_ambiguity ** 1.5) * 0.35

        # 3. Adversary Maslow oscillation penalty (Psychological task-switching disruption)
        oscillation_penalty = min(0.30, maslow_state_oscillation_rate * 0.40)

        # 4. Multi-task saturation penalty
        task_penalty = min(0.30, (concurrent_pending_tasks / 5.0) * 0.20)

        # Aggregate Decision Hesitation Index (0.0 to 1.0)
        raw_dhi = density_penalty + ambiguity_penalty + oscillation_penalty + task_penalty
        dhi = float(np.clip(raw_dhi, 0.05, 1.0))

        # Predicted Operator Reaction Time (ORT in milliseconds)
        # Exponential curve as operator approaches saturation
        ort_multiplier = 1.0 + (dhi ** 2.2) * 5.5
        predicted_ort_ms = round(self.base_reaction_ms * ort_multiplier * self.fatigue_factor, 1)

        # Classify bottleneck severity
        if dhi < 0.35:
            level = SaturationLevel.NOMINAL
            mitigation_advisory = "Standard ROE: Operator latency well within defensive intercept envelope."
        elif dhi < 0.70:
            level = SaturationLevel.ELEVATED
            mitigation_advisory = "Elevated cognitive friction: Suggest autonomous sensor handover to reduce manual track tagging."
        else:
            level = SaturationLevel.COGNITIVE_BOTTLENECK
            mitigation_advisory = (
                "CRITICAL BOTTLENECK DETECTED: Operator hesitation window exceeds intercept safety threshold (>6.0s). "
                "Adversary is weaponizing psychological oscillation. Activate Cognitive Resilience Architecture (CRA)."
            )

        return {
            "decision_hesitation_index": round(dhi, 3),
            "predicted_reaction_time_ms": predicted_ort_ms,
            "saturation_level": level.value,
            "mitigation_advisory": mitigation_advisory,
            "components": {
                "density_penalty": round(float(density_penalty), 3),
                "ambiguity_penalty": round(float(ambiguity_penalty), 3),
                "oscillation_penalty": round(float(oscillation_penalty), 3),
                "task_penalty": round(float(task_penalty), 3),
            },
            "vulnerability_window_seconds": round(predicted_ort_ms / 1000.0, 2),
        }
