"""
MAVLink / ArduPilot SITL (Software In The Loop) Virtual Simulation Adapter.
Translates open aerospace telemetry streams into Lattice Common Operating Picture (COP) TrackEntities.
"""

from __future__ import annotations

import math
import struct
from typing import List, Optional

from pydantic import BaseModel, Field

from lattice_cognitive.twin.schema import TrackEntity, Classification
from lattice_cognitive.twin.mock_sdk import MockLatticeTwin

CRC_EXTRA_GLOBAL_POSITION_INT = 104


def mavlink_crc_accumulate(byte_val: int, crc: int) -> int:
    """Official MAVLink ITU X.25 CRC-16 checksum accumulator."""
    tmp = (byte_val ^ (crc & 0xFF)) & 0xFF
    tmp = (tmp ^ ((tmp << 4) & 0xFF)) & 0xFF
    return ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ ((tmp >> 4) & 0x0F)) & 0xFFFF


def mavlink_crc_calculate(buf: bytes | bytearray, crc_extra: int) -> int:
    """Calculates official MAVLink X.25 CRC-16 seeded with message CRC_EXTRA."""
    crc = 0xFFFF
    for b in buf:
        crc = mavlink_crc_accumulate(b, crc)
    crc = mavlink_crc_accumulate(crc_extra, crc)
    return crc

try:
    import lattice_cognitive_rs as lrs
    RUST_CORE_AVAILABLE = True
except ImportError:
    lrs = None
    RUST_CORE_AVAILABLE = False


class VirtualSwarmScenario(BaseModel):
    """Configuration for an autonomous adversarial drone swarm simulation."""
    num_drones: int = Field(default=20, description="Total virtual drones in the swarm")
    feint_radius_m: float = Field(default=3500.0, description="Orbit standoff radius in meters")
    origin_lat: float = Field(default=33.5, description="Tactical range latitude baseline")
    origin_lon: float = Field(default=-116.5, description="Tactical range longitude baseline")
    oscillation_period_s: float = Field(default=8.0, description="Swarm feint oscillation cycle time")


class SitlAdapter:
    """
    Bridges virtual defense simulation engines (ArduPilot SITL, PX4, JSBSim)
    into the Lattice Cognitive Mock Sandbox Twin.
    """

    def __init__(self, origin_lat: float = 33.5, origin_lon: float = -116.5) -> None:
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self.use_rust = RUST_CORE_AVAILABLE

        if self.use_rust and lrs is not None:
            self._rust_engine = lrs.MavlinkSitlEngine(origin_lat, origin_lon)
        else:
            self._rust_engine = None

    def parse_mavlink_stream(self, raw_bytes: bytes) -> List[TrackEntity]:
        """
        Parses binary MAVLink v1/v2 stream into Lattice COP TrackEntities.
        Uses zero-copy Rust kernel when available (60M+ ops/sec).
        """
        if self.use_rust and self._rust_engine is not None:
            batch, count = self._rust_engine.parse_packets(raw_bytes)
            tracks = []
            meters_per_deg_lat = 111319.5
            meters_per_deg_lon = 111319.5 * math.cos(math.radians(self.origin_lat))

            for i in range(count):
                pt = batch.get(i)
                if pt is None:
                    continue

                lat = self.origin_lat + (pt.y / meters_per_deg_lat)
                lon = self.origin_lon + (pt.x / meters_per_deg_lon)

                class_map = {
                    0: Classification.FRIENDLY,
                    1: Classification.UNKNOWN,
                    2: Classification.SUSPECT,
                    3: Classification.HOSTILE,
                    4: Classification.DECOY,
                }
                classification = class_map.get(pt.classification, Classification.UNKNOWN)
                speed = pt.speed()

                tracks.append(
                    TrackEntity(
                        entity_id=f"SITL-UAV-{pt.id:03d}",
                        callsign=f"SITL-SWARM-{pt.id:02d}",
                        classification=classification,
                        latitude=lat,
                        longitude=lon,
                        altitude_m=max(10.0, pt.z),
                        speed_mps=speed,
                        heading_deg=math.degrees(math.atan2(pt.vx, pt.vy)) % 360.0,
                        rcs_sqm=0.08,
                    )
                )
            return tracks

        # Fallback pure-Python MAVLink parser
        return self._python_parse_mavlink(raw_bytes)

    def _python_parse_mavlink(self, raw_bytes: bytes) -> List[TrackEntity]:
        tracks = []
        idx = 0
        buf_len = len(raw_bytes)

        while idx < buf_len:
            magic = raw_bytes[idx]
            if magic == 0xFE and idx + 36 <= buf_len:
                let_len = raw_bytes[idx + 1]
                sys_id = raw_bytes[idx + 3]
                msg_id = raw_bytes[idx + 5]
                if msg_id == 33 and let_len >= 28: # GLOBAL_POSITION_INT
                    expected_crc = raw_bytes[idx + 34] | (raw_bytes[idx + 35] << 8)
                    computed_crc = mavlink_crc_calculate(
                        raw_bytes[idx + 1 : idx + 34],
                        CRC_EXTRA_GLOBAL_POSITION_INT,
                    )
                    if expected_crc == computed_crc:
                        payload = raw_bytes[idx + 6 : idx + 34]
                        time_boot_ms, lat_e7, lon_e7, alt_mm, rel_alt_mm, vx_cms, vy_cms, vz_cms, _ = struct.unpack(
                            "<IiiiihhhH", payload
                        )
                        lat_deg = lat_e7 * 1e-7
                        lon_deg = lon_e7 * 1e-7
                        vx = vx_cms / 100.0
                        vy = vy_cms / 100.0
                        speed = math.sqrt(vx * vx + vy * vy)

                        tracks.append(
                            TrackEntity(
                                entity_id=f"SITL-UAV-{sys_id:03d}",
                                callsign=f"SITL-SWARM-{sys_id:02d}",
                                classification=Classification.UNKNOWN,
                                latitude=lat_deg,
                                longitude=lon_deg,
                                altitude_m=max(10.0, rel_alt_mm / 1000.0),
                                speed_mps=speed,
                                heading_deg=math.degrees(math.atan2(vx, vy)) % 360.0,
                                rcs_sqm=0.08,
                            )
                        )
                idx += 36
            else:
                idx += 1
        return tracks

    def generate_virtual_swarm_telemetry(
        self,
        scenario: VirtualSwarmScenario,
        elapsed_s: float,
    ) -> bytes:
        """
        Generates simulated MAVLink telemetry packets for an ArduPilot multi-UAV swarm.
        Allows validating cognitive saturation against 20+ coordinated drones virtually.
        """
        if self.use_rust and self._rust_engine is not None:
            raw = self._rust_engine.generate_synthetic_sitl_swarm(
                scenario.num_drones, elapsed_s, scenario.feint_radius_m
            )
            return bytes(raw)

        # Fallback pure-Python synthetic generation
        packet_bytes = bytearray()
        meters_per_deg_lat = 111319.5
        meters_per_deg_lon = 111319.5 * math.cos(math.radians(scenario.origin_lat))

        for i in range(1, scenario.num_drones + 1):
            phase = i * (2.0 * math.pi / scenario.num_drones)
            angle = (elapsed_s * 0.1) + phase
            x_m = scenario.feint_radius_m * math.cos(angle)
            y_m = scenario.feint_radius_m * math.sin(angle)
            alt_m = 150.0 + 30.0 * math.sin(angle * 2.0)

            vx_cms = int(-scenario.feint_radius_m * 0.1 * math.sin(angle) * 100.0)
            vy_cms = int(scenario.feint_radius_m * 0.1 * math.cos(angle) * 100.0)

            lat_e7 = int((scenario.origin_lat + (y_m / meters_per_deg_lat)) * 1e7)
            lon_e7 = int((scenario.origin_lon + (x_m / meters_per_deg_lon)) * 1e7)
            alt_mm = int(alt_m * 1000.0)

            payload = struct.pack(
                "<IiiiihhhH",
                int(elapsed_s * 1000.0),
                lat_e7,
                lon_e7,
                alt_mm,
                alt_mm,
                max(-32768, min(32767, vx_cms)),
                max(-32768, min(32767, vy_cms)),
                0,
                0,
            )

            frame = bytearray([0xFE, 28, i, i, 1, 33])
            frame.extend(payload)
            crc = mavlink_crc_calculate(frame[1:], CRC_EXTRA_GLOBAL_POSITION_INT)
            frame.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            packet_bytes.extend(frame)

        return bytes(packet_bytes)

    def inject_swarm_into_twin(
        self,
        twin: MockLatticeTwin,
        scenario: VirtualSwarmScenario,
        elapsed_s: float,
    ) -> List[TrackEntity]:
        """
        Generates and ingests virtual swarm telemetry directly into the Lattice Twin COP.
        """
        raw_stream = self.generate_virtual_swarm_telemetry(scenario, elapsed_s)
        tracks = self.parse_mavlink_stream(raw_stream)
        for track in tracks:
            twin.publish_track(track)
        return tracks
