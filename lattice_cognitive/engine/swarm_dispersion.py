"""
Adversary Decoy Swarm Spatial Dispersion & RCS Scintillation Engine.
Simulates coordinated electronic and kinetic swarm dispersion to saturate
operator visual working memory chunks under Hick-Hyman Law.
"""

from __future__ import annotations
import math
import numpy as np
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from lattice_cognitive.twin.schema import TrackEntity, Classification


class DecoySwarmCluster(BaseModel):
    """
    Simulated swarm of coordinated decoys executing spatial blooming and RCS fluctuation.
    """
    cluster_id: str
    centroid_lat: float
    centroid_lon: float
    base_altitude_m: float
    num_decoys: int = Field(6, ge=1, le=64)
    dispersion_radius_m: float = Field(1200.0, description="Spatial spread of swarm elements")
    rcs_scintillation_range: tuple[float, float] = (0.01, 1.8)

    def generate_dispersed_tracks(self) -> List[TrackEntity]:
        """
        Generates individual decoy tracks scattered across the dispersion radius,
        inducing maximum visual chunk load on the supervisory operator.
        """
        tracks = []
        angle_step = (2 * math.pi) / self.num_decoys

        for i in range(self.num_decoys):
            angle = i * angle_step + np.random.uniform(-0.15, 0.15)
            dist_m = self.dispersion_radius_m * np.random.uniform(0.6, 1.0)

            # Approximate meters to degrees
            d_lat = (dist_m * math.cos(angle)) / 111_000.0
            d_lon = (dist_m * math.sin(angle)) / (111_000.0 * math.cos(math.radians(self.centroid_lat)))

            rcs = float(np.random.uniform(*self.rcs_scintillation_range))
            alt = self.base_altitude_m + float(np.random.uniform(-150.0, 150.0))

            tracks.append(
                TrackEntity(
                    entity_id=f"{self.cluster_id}-unit-{i+1}",
                    callsign=f"DECOY-{self.cluster_id[-4:].upper()}-{i+1}",
                    classification=Classification.DECOY if rcs < 0.2 else Classification.SUSPECT,
                    confidence=0.55 if rcs >= 0.2 else 0.85,
                    latitude=round(self.centroid_lat + d_lat, 6),
                    longitude=round(self.centroid_lon + d_lon, 6),
                    altitude_m=round(alt, 1),
                    speed_mps=140.0 + float(np.random.uniform(-15.0, 15.0)),
                    heading_deg=round(math.degrees(angle) % 360, 1),
                    rcs_sqm=round(rcs, 3),
                )
            )
        return tracks
