"""
Mock Lattice Twin SDK.
Provides an isolated, in-memory simulation twin of the Anduril Lattice OS API.
Allows synthetic track injection, sensor fusion streams, and human-in-the-loop task dispatch.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from lattice_cognitive.twin.schema import (
    TrackEntity,
    Classification,
    SensorDomain,
    LatticeTask,
    TaskType,
    TaskStatus,
)


class MockLatticeTwin:
    """
    Developer sandbox twin for Anduril Lattice OS.
    Runs entirely in memory without contacting external or classified networks.
    """

    def __init__(self, airspace_name: str = "Sector-7-Mojave-Range"):
        self.airspace_name = airspace_name
        self.tracks: Dict[str, TrackEntity] = {}
        self.tasks: Dict[str, LatticeTask] = {}
        self.event_log: List[Dict[str, Any]] = []

        # Bootstrap friendly assets
        self._bootstrap_friendly_defenders()

    def _bootstrap_friendly_defenders(self) -> None:
        """Initialize standard Anduril autonomous sentries (Ghost / Anvil equivalents)."""
        defenders = [
            TrackEntity(
                entity_id="asset-anvil-01",
                callsign="ANVIL-INTERCEPTOR-ALPHA",
                classification=Classification.FRIENDLY,
                confidence=1.0,
                latitude=34.0200,
                longitude=-118.2200,
                altitude_m=2000.0,
                speed_mps=310.0,
                heading_deg=0.0,
                rcs_sqm=0.8,
            ),
            TrackEntity(
                entity_id="asset-ghost-01",
                callsign="GHOST-SENTRY-TOWER-04",
                classification=Classification.FRIENDLY,
                confidence=1.0,
                latitude=34.0800,
                longitude=-118.2800,
                altitude_m=150.0,
                speed_mps=0.0,
                heading_deg=90.0,
                rcs_sqm=5.0,
                sensor_detections=[SensorDomain.RADAR, SensorDomain.EO_IR, SensorDomain.RF_EMISSION],
            ),
        ]
        for defender in defenders:
            self.tracks[defender.entity_id] = defender

    def publish_track(self, track: TrackEntity) -> TrackEntity:
        """Inject or update an entity track in the Lattice Common Operating Picture."""
        self.tracks[track.entity_id] = track
        self.event_log.append({
            "event": "TRACK_UPDATED",
            "entity_id": track.entity_id,
            "classification": track.classification.value,
            "altitude_m": track.altitude_m,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return track

    def get_track(self, entity_id: str) -> Optional[TrackEntity]:
        return self.tracks.get(entity_id)

    def list_tracks(self) -> List[TrackEntity]:
        return list(self.tracks.values())

    def dispatch_task(
        self,
        task_type: TaskType,
        target_entity_id: str,
        assigned_asset_id: Optional[str] = "asset-anvil-01",
    ) -> LatticeTask:
        """
        Creates a tactical assignment in Lattice requiring operator authorization.
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = LatticeTask(
            task_id=task_id,
            task_type=task_type,
            target_entity_id=target_entity_id,
            assigned_asset_id=assigned_asset_id,
            status=TaskStatus.PENDING_APPROVAL,
        )
        self.tasks[task_id] = task
        self.event_log.append({
            "event": "TASK_DISPATCHED",
            "task_id": task_id,
            "task_type": task_type.value,
            "target": target_entity_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return task

    def operator_approve_task(
        self,
        task_id: str,
        operator_id: str = "OP-CALLSIGN-RAVEN",
        simulated_hesitation_ms: float = 3400.0,
    ) -> LatticeTask:
        """
        Simulate human operator reviewing and confirming authorization for a task.
        Records operator hesitation latency.
        """
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found in Lattice Twin")

        task = self.tasks[task_id]
        task.status = TaskStatus.APPROVED
        task.operator_id = operator_id
        task.approved_at = datetime.now(timezone.utc)
        task.latency_ms = simulated_hesitation_ms

        self.event_log.append({
            "event": "TASK_APPROVED_BY_OPERATOR",
            "task_id": task_id,
            "operator": operator_id,
            "hesitation_ms": simulated_hesitation_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return task

    def get_active_tasks(self) -> List[LatticeTask]:
        return [t for t in self.tasks.values() if t.status in (TaskStatus.PENDING_APPROVAL, TaskStatus.EXECUTING)]
