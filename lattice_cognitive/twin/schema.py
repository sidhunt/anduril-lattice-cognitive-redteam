"""
Schema definitions for Lattice Sandbox Twin.
Models entity tracking, sensor observations, and tasking protocols
mirroring Anduril Lattice API semantics.
"""

from __future__ import annotations
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class Classification(str, Enum):
    FRIENDLY = "FRIENDLY"
    UNKNOWN = "UNKNOWN"
    SUSPECT = "SUSPECT"
    HOSTILE = "HOSTILE"
    DECOY = "DECOY"


class SensorDomain(str, Enum):
    RADAR = "RADAR"
    EO_IR = "EO_IR"
    RF_EMISSION = "RF_EMISSION"
    ACOUSTIC = "ACOUSTIC"


class TrackEntity(BaseModel):
    """
    Representation of an airborne or surface track in the Lattice Twin Common Operating Picture (COP).
    """
    entity_id: str
    callsign: str
    classification: Classification = Classification.UNKNOWN
    confidence: float = Field(0.50, ge=0.0, le=1.0)
    latitude: float
    longitude: float
    altitude_m: float
    speed_mps: float
    heading_deg: float
    rcs_sqm: float = Field(1.5, description="Radar Cross Section in m^2")
    active_countermeasure: Optional[str] = None
    sensor_detections: List[SensorDomain] = Field(default_factory=lambda: [SensorDomain.RADAR])
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskType(str, Enum):
    IDENTIFY = "IDENTIFY"
    TRACK = "TRACK"
    INTERCEPT = "INTERCEPT"
    EW_JAM = "EW_JAM"
    ESCORT = "ESCORT"


class TaskStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"   # Waiting for human operator authorization
    APPROVED = "APPROVED"                   # Human operator confirmed action
    EXECUTING = "EXECUTING"                 # Sentry / Interceptor en route
    COMPLETED = "COMPLETED"                 # Mission objective met
    ABORTED = "ABORTED"                     # Cancelled due to timeout or ambiguity


class LatticeTask(BaseModel):
    """
    Tactical assignment dispatched by Lattice Core or requested from human-in-the-loop operator.
    """
    task_id: str
    task_type: TaskType
    target_entity_id: str
    assigned_asset_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING_APPROVAL
    operator_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    latency_ms: Optional[float] = None
    hesitation_score: Optional[float] = None
