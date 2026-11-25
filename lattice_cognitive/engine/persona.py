"""
Adversary Persona Module.
Orchestrates motivation profiles, Markov transitions, and tactical actions for autonomous actors.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from lattice_cognitive.engine.maslow import MaslowLevel, MotivationProfile
from lattice_cognitive.engine.markov_chain import AdversarialMarkovChain


class AdversaryPersona:
    """
    Simulated adversary combatant or autonomous drone swarm node.
    Combines Maslow motivation weights with real-time Markov state evolution.
    """

    def __init__(
        self,
        persona_id: Optional[str] = None,
        callsign: str = "GHOST-TRACK-ALPHA",
        profile: Optional[MotivationProfile] = None,
    ):
        self.persona_id = persona_id or f"adv-{uuid.uuid4().hex[:8]}"
        self.callsign = callsign
        self.profile = profile or MotivationProfile()
        self.markov_chain = AdversarialMarkovChain(self.profile)

        # Kinetic state
        self.latitude: float = 34.0522
        self.longitude: float = -118.2437
        self.altitude_m: float = 3500.0
        self.heading_deg: float = 45.0
        self.speed_mps: float = 220.0

    @property
    def current_state(self) -> MaslowLevel:
        return self.markov_chain.current_state

    def observe_lattice(
        self,
        radar_lock: bool,
        intercept_dispatched: bool,
        operator_hesitation_ms: float,
        decoy_survived: bool = True,
    ) -> None:
        """Process incoming defensive telemetry from the Lattice Twin."""
        self.markov_chain.update_from_lattice_observation(
            radar_lock=radar_lock,
            intercept_dispatched=intercept_dispatched,
            operator_hesitation_ms=operator_hesitation_ms,
            decoy_survived=decoy_survived,
        )

    def execute_tick(self, delta_time_s: float = 1.0) -> Dict[str, Any]:
        """
        Advance psychological state and apply resulting tactical directive to kinetics.
        """
        new_state, transition_info = self.markov_chain.step()
        directive = self.markov_chain.get_tactical_directive()

        # Update simulated flight parameters
        self.altitude_m = max(50.0, self.altitude_m + directive["altitude_offset_m"] * (delta_time_s / 60.0))
        effective_speed = self.speed_mps * directive["speed_multiplier"]

        # Approximate position displacement
        lat_delta = (effective_speed * delta_time_s) / 111_000.0
        self.latitude += lat_delta

        return {
            "persona_id": self.persona_id,
            "callsign": self.callsign,
            "maslow_state": new_state.value,
            "directive": directive,
            "kinetics": {
                "latitude": round(self.latitude, 6),
                "longitude": round(self.longitude, 6),
                "altitude_m": round(self.altitude_m, 1),
                "speed_mps": round(effective_speed, 1),
            },
            "transition": transition_info,
        }
