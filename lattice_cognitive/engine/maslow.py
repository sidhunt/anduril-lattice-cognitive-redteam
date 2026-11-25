"""
Maslow Motivation Engine for Adversarial Actor Simulation.
Maps psychological need hierarchies to tactical defense maneuvers.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field


class MaslowLevel(str, Enum):
    """
    Five-tier hierarchical motivation states for adversarial defense actors.
    Each tier dictates behavioral priority and tolerance for risk.
    """
    SURVIVAL = "SURVIVAL"                      # Tier 1: Kinetic survival, chaff/flare, terrain masking
    SECURITY = "SECURITY"                      # Tier 2: Low-observability, radar silence, standoff standoff
    BELONGING = "BELONGING"                    # Tier 3: Swarm cohesion, mesh relay, mutual escort
    ESTEEM = "ESTEEM"                          # Tier 4: Radar saturation, feints, high-value asset targeting
    SELF_ACTUALIZATION = "SELF_ACTUALIZATION"  # Tier 5: Doctrinal mission completion, terminal attack vector


class MotivationProfile(BaseModel):
    """
    Defines the baseline psychological drives and risk tolerances of an adversary doctrine.
    """
    name: str = "Asymmetric-Recon-Drone"
    doctrine: str = "Anti-Access / Area-Denial (A2/AD) Infiltration"
    base_weights: Dict[MaslowLevel, float] = Field(
        default_factory=lambda: {
            MaslowLevel.SURVIVAL: 0.35,
            MaslowLevel.SECURITY: 0.25,
            MaslowLevel.BELONGING: 0.15,
            MaslowLevel.ESTEEM: 0.15,
            MaslowLevel.SELF_ACTUALIZATION: 0.10,
        }
    )
    risk_tolerance: float = Field(0.40, ge=0.0, le=1.0, description="Willingness to enter radar coverage")
    swarm_affinity: float = Field(0.60, ge=0.0, le=1.0, description="Tendency to cluster with decoys")

    def normalize(self) -> None:
        """Ensure all weights sum to 1.0."""
        total = sum(self.base_weights.values())
        if total > 0:
            for k in self.base_weights:
                self.base_weights[k] /= total

    def compute_active_weights(
        self,
        threat_proximity: float,
        lattice_task_intensity: float,
        swarm_health_ratio: float,
    ) -> Dict[MaslowLevel, float]:
        """
        Dynamically adjusts motivation weights based on live battlefield stimuli:
        - threat_proximity: 0.0 (far) to 1.0 (immediate kinetic threat)
        - lattice_task_intensity: 0.0 (passive) to 1.0 (heavy intercept tasking)
        - swarm_health_ratio: 0.0 (all allies destroyed) to 1.0 (full swarm intact)
        """
        weights = dict(self.base_weights)

        # High kinetic threat spikes Survival (Tier 1)
        if threat_proximity > 0.6:
            spike = (threat_proximity - 0.6) * 1.5
            weights[MaslowLevel.SURVIVAL] += spike
            weights[MaslowLevel.ESTEEM] = max(0.01, weights[MaslowLevel.ESTEEM] - spike * 0.5)

        # High sensor tasking from Lattice forces Security (Tier 2) or Esteem feints (Tier 4)
        if lattice_task_intensity > 0.7:
            if self.risk_tolerance > 0.5:
                weights[MaslowLevel.ESTEEM] += 0.30  # Feint to distract operator
            else:
                weights[MaslowLevel.SECURITY] += 0.35  # Retreat into clutter

        # Declining swarm health drives either Belonging panic or terminal Self-Actualization
        if swarm_health_ratio < 0.3:
            if self.risk_tolerance >= 0.7:
                weights[MaslowLevel.SELF_ACTUALIZATION] += 0.50  # Martyrdom / terminal strike
            else:
                weights[MaslowLevel.SURVIVAL] += 0.40  # Full abort

        # Re-normalize
        total = sum(weights.values())
        return {k: round(v / total, 4) for k, v in weights.items()}
