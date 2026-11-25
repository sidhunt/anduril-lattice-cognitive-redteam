"""
Markov State Transition Engine for Adversarial Actors.
Maintains and dynamically updates the transition probability matrix
governing adversary psychological shifts under active Lattice surveillance.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple
from lattice_cognitive.engine.maslow import MaslowLevel, MotivationProfile


LEVELS = list(MaslowLevel)
N_STATES = len(LEVELS)
STATE_TO_IDX = {level: i for i, level in enumerate(LEVELS)}
IDX_TO_STATE = {i: level for i, level in enumerate(LEVELS)}


class AdversarialMarkovChain:
    """
    Stochastic state machine representing adversary cognitive transitions.
    Transitions evolve in real time based on observed Lattice OS behavior.
    """

    def __init__(self, profile: MotivationProfile):
        self.profile = profile
        self.current_state: MaslowLevel = MaslowLevel.SECURITY
        self.history: List[MaslowLevel] = [self.current_state]

        # Initialize base transition matrix P[i, j] = P(Next=j | Current=i)
        self.transition_matrix = self._build_prior_matrix()

    def _build_prior_matrix(self) -> np.ndarray:
        """
        Constructs initial transition probabilities biased by baseline motivation weights.
        """
        matrix = np.zeros((N_STATES, N_STATES), dtype=np.float64)
        weights = [self.profile.base_weights[level] for level in LEVELS]

        for i in range(N_STATES):
            for j in range(N_STATES):
                # Diagonal persistence + motivation pull
                persistence = 0.50 if i == j else 0.125
                matrix[i, j] = persistence * weights[j]

            # Normalize row
            row_sum = np.sum(matrix[i])
            if row_sum > 0:
                matrix[i] /= row_sum

        return matrix

    def update_from_lattice_observation(
        self,
        radar_lock: bool,
        intercept_dispatched: bool,
        operator_hesitation_ms: float,
        decoy_survived: bool,
    ) -> None:
        """
        Bayesian update of the transition matrix given Lattice Twin sensor & task telemetry:
        - radar_lock: increases transition probability to SURVIVAL or SECURITY
        - intercept_dispatched: escalates either to terminal SELF_ACTUALIZATION or SURVIVAL
        - operator_hesitation_ms: if high (> 5000ms), adversary capitalizes by shifting to ESTEEM
        - decoy_survived: reinforces BELONGING / swarm reliance
        """
        learning_rate = 0.15
        target_boost = np.zeros(N_STATES, dtype=np.float64)

        if radar_lock:
            target_boost[STATE_TO_IDX[MaslowLevel.SURVIVAL]] += 0.40
            target_boost[STATE_TO_IDX[MaslowLevel.SECURITY]] += 0.30

        if intercept_dispatched:
            if self.profile.risk_tolerance > 0.6:
                target_boost[STATE_TO_IDX[MaslowLevel.SELF_ACTUALIZATION]] += 0.50
            else:
                target_boost[STATE_TO_IDX[MaslowLevel.SURVIVAL]] += 0.60

        if operator_hesitation_ms > 5000:
            # Operator is hesitating -> adversary detects slow loop, exploits with aggressive posturing
            target_boost[STATE_TO_IDX[MaslowLevel.ESTEEM]] += 0.45

        if decoy_survived:
            target_boost[STATE_TO_IDX[MaslowLevel.BELONGING]] += 0.35

        # Apply update across all transition rows with damping
        if np.sum(target_boost) > 0:
            target_boost /= np.sum(target_boost)
            current_idx = STATE_TO_IDX[self.current_state]
            self.transition_matrix[current_idx] = (
                (1.0 - learning_rate) * self.transition_matrix[current_idx]
                + learning_rate * target_boost
            )
            # Re-normalize row
            self.transition_matrix[current_idx] /= np.sum(self.transition_matrix[current_idx])

    def step(self) -> Tuple[MaslowLevel, Dict[str, Any]]:
        """
        Advances the Markov chain by sampling the next state according to P(Next | Current).
        Returns (new_state, step_telemetry).
        """
        curr_idx = STATE_TO_IDX[self.current_state]
        probabilities = self.transition_matrix[curr_idx]

        next_idx = np.random.choice(N_STATES, p=probabilities)
        next_state = IDX_TO_STATE[next_idx]

        previous_state = self.current_state
        self.current_state = next_state
        self.history.append(next_state)

        return next_state, {
            "from_state": previous_state.value,
            "to_state": next_state.value,
            "transition_probability": float(probabilities[next_idx]),
            "state_vector": {LEVELS[i].value: round(float(p), 4) for i, p in enumerate(probabilities)},
        }

    def get_tactical_directive(self) -> Dict[str, Any]:
        """
        Translates current psychological Maslow state into concrete kinetic / electronic directives.
        """
        directives = {
            MaslowLevel.SURVIVAL: {
                "altitude_offset_m": -800,  # Dive to terrain clutter
                "speed_multiplier": 1.4,     # Max continuous thrust
                "emissions_mode": "SILENT",
                "countermeasures": "CHAFF_DEPLOYED",
                "tactic": "Kinetic Evasion & Clutter Infiltration",
            },
            MaslowLevel.SECURITY: {
                "altitude_offset_m": 0,
                "speed_multiplier": 0.8,     # Loiter mode
                "emissions_mode": "LPI_RADAR",
                "countermeasures": "STANDOFF_MAINTAINED",
                "tactic": "Perimeter Standoff & Emission Control",
            },
            MaslowLevel.BELONGING: {
                "altitude_offset_m": 100,
                "speed_multiplier": 1.0,
                "emissions_mode": "MESH_SYNC",
                "countermeasures": "SWARM_FORMATION",
                "tactic": "Decoy Synchronization & Mesh Relay",
            },
            MaslowLevel.ESTEEM: {
                "altitude_offset_m": 500,    # Climb to increase radar visibility
                "speed_multiplier": 1.2,
                "emissions_mode": "ACTIVE_PULSE_SATURATION",
                "countermeasures": "RADAR_FEINT",
                "tactic": "Sensor Saturation & Command Posturing",
            },
            MaslowLevel.SELF_ACTUALIZATION: {
                "altitude_offset_m": -200,
                "speed_multiplier": 1.6,     # Terminal dash
                "emissions_mode": "TERMINAL_HOMING",
                "countermeasures": "OBJECTIVE_OVERRIDE",
                "tactic": "Terminal Kinetic Vector & Mission Fulfillment",
            },
        }
        return directives[self.current_state]
