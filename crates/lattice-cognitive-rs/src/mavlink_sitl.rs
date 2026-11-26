use byteorder::{LittleEndian, ReadBytesExt};
use std::io::Cursor;
use crate::track::{Track, TrackBatch};

pub const MAVLINK_V1_STX: u8 = 0xFE;
pub const MAVLINK_V2_STX: u8 = 0xFD;

pub const MSG_ID_HEARTBEAT: u32 = 0;
pub const MSG_ID_ATTITUDE: u32 = 30;
pub const MSG_ID_GLOBAL_POSITION_INT: u32 = 33;

/// Ingested MAVLink Telemetry Point.
#[derive(Debug, Clone, Default)]
pub struct MavlinkGlobalPosition {
    pub time_boot_ms: u32,
    pub lat: i32, // degE7
    pub lon: i32, // degE7
    pub alt: i32, // mm (MSL)
    pub relative_alt: i32, // mm (above ground)
    pub vx: i16, // cm/s
    pub vy: i16, // cm/s
    pub vz: i16, // cm/s
    pub hdg: u16, // cdeg
    pub sys_id: u8,
}

impl MavlinkGlobalPosition {
    /// Convert to local metric Cartesian Track relative to origin (lat0, lon0).
    pub fn to_track(&self, origin_lat: f64, origin_lon: f64) -> Track {
        let lat_deg = (self.lat as f64) * 1e-7;
        let lon_deg = (self.lon as f64) * 1e-7;

        // Flat-earth approximation (valid for 100km radius tactical areas)
        const METERS_PER_DEG_LAT: f64 = 111319.5;
        let meters_per_deg_lon = 111319.5 * (origin_lat.to_radians()).cos();

        let x = (lon_deg - origin_lon) * meters_per_deg_lon;
        let y = (lat_deg - origin_lat) * METERS_PER_DEG_LAT;
        let z = (self.relative_alt as f64) / 1000.0;

        let vx = (self.vx as f64) / 100.0;
        let vy = (self.vy as f64) / 100.0;
        let vz = (self.vz as f64) / 100.0;

        Track::new(
            self.sys_id as u64,
            x,
            y,
            z,
            vx,
            vy,
            vz,
            0.15, // Low initial sensor ambiguity for SITL
            1,    // UNKNOWN track upon initial detection
            self.time_boot_ms as u64,
        )
    }
}

/// SITL MAVLink Stream Parser and Swarm Generator.
#[derive(Debug, Clone)]
pub struct MavlinkSitlEngine {
    pub origin_lat: f64,
    pub origin_lon: f64,
}

impl Default for MavlinkSitlEngine {
    fn default() -> Self {
        Self {
            origin_lat: 33.5000, // Tactical range baseline (e.g. Edwards AFB / Yuma)
            origin_lon: -116.5000,
        }
    }
}

impl MavlinkSitlEngine {
    pub fn new(origin_lat: f64, origin_lon: f64) -> Self {
        Self {
            origin_lat,
            origin_lon,
        }
    }

    /// Parse raw MAVLink buffer into TrackBatch.
    pub fn parse_packets(&self, buffer: &[u8], batch: &mut TrackBatch) -> usize {
        let mut parsed_count = 0;
        let mut idx = 0;

        while idx < buffer.len() {
            let magic = buffer[idx];
            if magic == MAVLINK_V1_STX {
                if idx + 6 > buffer.len() {
                    break;
                }
                let payload_len = buffer[idx + 1] as usize;
                let packet_len = 6 + payload_len + 2; // header + payload + checksum
                if idx + packet_len > buffer.len() {
                    break;
                }

                let sys_id = buffer[idx + 3];
                let msg_id = buffer[idx + 5] as u32;

                if msg_id == MSG_ID_GLOBAL_POSITION_INT && payload_len >= 28 {
                    let payload = &buffer[idx + 6..idx + 6 + 28];
                    if let Ok(pos) = Self::decode_global_position(payload, sys_id) {
                        batch.push(pos.to_track(self.origin_lat, self.origin_lon));
                        parsed_count += 1;
                    }
                }
                idx += packet_len;
            } else if magic == MAVLINK_V2_STX {
                if idx + 10 > buffer.len() {
                    break;
                }
                let payload_len = buffer[idx + 1] as usize;
                let packet_len = 10 + payload_len + 2; // header + payload + checksum
                if idx + packet_len > buffer.len() {
                    break;
                }

                let sys_id = buffer[idx + 5];
                let msg_id = (buffer[idx + 7] as u32)
                    | ((buffer[idx + 8] as u32) << 8)
                    | ((buffer[idx + 9] as u32) << 16);

                if msg_id == MSG_ID_GLOBAL_POSITION_INT && payload_len >= 28 {
                    let payload = &buffer[idx + 10..idx + 10 + 28];
                    if let Ok(pos) = Self::decode_global_position(payload, sys_id) {
                        batch.push(pos.to_track(self.origin_lat, self.origin_lon));
                        parsed_count += 1;
                    }
                }
                idx += packet_len;
            } else {
                idx += 1;
            }
        }

        parsed_count
    }

    fn decode_global_position(payload: &[u8], sys_id: u8) -> Result<MavlinkGlobalPosition, ()> {
        let mut rdr = Cursor::new(payload);
        let time_boot_ms = rdr.read_u32::<LittleEndian>().map_err(|_| ())?;
        let lat = rdr.read_i32::<LittleEndian>().map_err(|_| ())?;
        let lon = rdr.read_i32::<LittleEndian>().map_err(|_| ())?;
        let alt = rdr.read_i32::<LittleEndian>().map_err(|_| ())?;
        let relative_alt = rdr.read_i32::<LittleEndian>().map_err(|_| ())?;
        let vx = rdr.read_i16::<LittleEndian>().map_err(|_| ())?;
        let vy = rdr.read_i16::<LittleEndian>().map_err(|_| ())?;
        let vz = rdr.read_i16::<LittleEndian>().map_err(|_| ())?;
        let hdg = rdr.read_u16::<LittleEndian>().map_err(|_| ())?;

        Ok(MavlinkGlobalPosition {
            time_boot_ms,
            lat,
            lon,
            alt,
            relative_alt,
            vx,
            vy,
            vz,
            hdg,
            sys_id,
        })
    }

    /// Generates synthetic MAVLink v1 binary packets simulating an ArduPilot SITL swarm.
    /// Enables defense tech researchers to validate C2 hesitation loops virtually with 0 hardware.
    pub fn generate_synthetic_sitl_swarm(
        &self,
        num_drones: usize,
        elapsed_s: f64,
        feint_radius_m: f64,
    ) -> Vec<u8> {
        let mut packet_bytes = Vec::with_capacity(num_drones * 36);

        const METERS_PER_DEG_LAT: f64 = 111319.5;
        let meters_per_deg_lon = 111319.5 * (self.origin_lat.to_radians()).cos();

        for i in 1..=num_drones {
            let sys_id = i as u8;
            let phase = (i as f64) * (std::f64::consts::TAU / (num_drones as f64));
            let angle = (elapsed_s * 0.1) + phase;

            let x_m = feint_radius_m * angle.cos();
            let y_m = feint_radius_m * angle.sin();
            let alt_m = 150.0 + 30.0 * (angle * 2.0).sin();

            let vx_cms = (-feint_radius_m * 0.1 * angle.sin() * 100.0) as i16;
            let vy_cms = (feint_radius_m * 0.1 * angle.cos() * 100.0) as i16;

            let lat_deg = self.origin_lat + (y_m / METERS_PER_DEG_LAT);
            let lon_deg = self.origin_lon + (x_m / meters_per_deg_lon);

            let lat_e7 = (lat_deg * 1e7) as i32;
            let lon_e7 = (lon_deg * 1e7) as i32;
            let alt_mm = (alt_m * 1000.0) as i32;

            // Build MAVLink v1 frame for MSG_ID_GLOBAL_POSITION_INT (33)
            let mut payload = Vec::with_capacity(28);
            payload.extend_from_slice(&((elapsed_s * 1000.0) as u32).to_le_bytes()); // time_boot_ms
            payload.extend_from_slice(&lat_e7.to_le_bytes());
            payload.extend_from_slice(&lon_e7.to_le_bytes());
            payload.extend_from_slice(&alt_mm.to_le_bytes());
            payload.extend_from_slice(&alt_mm.to_le_bytes()); // relative_alt
            payload.extend_from_slice(&vx_cms.to_le_bytes());
            payload.extend_from_slice(&vy_cms.to_le_bytes());
            payload.extend_from_slice(&0i16.to_le_bytes()); // vz
            payload.extend_from_slice(&0u16.to_le_bytes()); // hdg

            // MAVLink v1 Header: STX, LEN, SEQ, SYSID, COMPID, MSGID
            let mut frame = Vec::with_capacity(6 + 28 + 2);
            frame.push(MAVLINK_V1_STX);
            frame.push(28); // payload len
            frame.push(sys_id); // seq
            frame.push(sys_id); // sysid
            frame.push(1); // compid
            frame.push(MSG_ID_GLOBAL_POSITION_INT as u8);
            frame.extend_from_slice(&payload);

            // Mock checksum bytes
            frame.push(0x55);
            frame.push(0xAA);

            packet_bytes.extend_from_slice(&frame);
        }

        packet_bytes
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mavlink_sitl_roundtrip() {
        let engine = MavlinkSitlEngine::new(33.5, -116.5);
        let raw = engine.generate_synthetic_sitl_swarm(5, 1.0, 2000.0);
        assert!(!raw.is_empty());

        let mut batch = TrackBatch::new();
        let parsed = engine.parse_packets(&raw, &mut batch);
        assert_eq!(parsed, 5);
        assert_eq!(batch.len(), 5);
        assert_eq!(batch.as_slice()[0].id, 1);
    }
}

