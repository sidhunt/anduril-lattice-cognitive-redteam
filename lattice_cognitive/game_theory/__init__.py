"""
Game-Theoretic Formulations of Command-and-Control (C2) Operator Hesitation.
Models Stackelberg leader-follower dynamics and Bayesian signaling games
under bounded rationality and Hick-Hyman cognitive latency limits.
"""

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

__all__ = [
    "StackelbergGameEngine",
    "AdversaryStrategy",
    "OperatorPayoffProfile",
    "EquilibriumResult",
    "BayesianSignalingGame",
    "SignalType",
    "ThreatType",
    "SignalingEquilibrium",
]
