use serde::{Deserialize, Serialize};

/// High-throughput C2 Radar / Sentry Track representation.
/// Compact #[repr(C)] memory layout enables zero-copy buffer sharing.
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Track {
    pub id: u64,
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub vx: f64,
    pub vy: f64,
    pub vz: f64,
    pub ambiguity: f64,
    pub classification: u8, // 0: FRIENDLY, 1: UNKNOWN, 2: SUSPECT, 3: HOSTILE, 4: DECOY
    pub timestamp_ms: u64,
}

impl Track {
    pub fn new(
        id: u64,
        x: f64,
        y: f64,
        z: f64,
        vx: f64,
        vy: f64,
        vz: f64,
        ambiguity: f64,
        classification: u8,
        timestamp_ms: u64,
    ) -> Self {
        Self {
            id,
            x,
            y,
            z,
            vx,
            vy,
            vz,
            ambiguity: ambiguity.clamp(0.0, 1.0),
            classification,
            timestamp_ms,
        }
    }

    #[inline(always)]
    pub fn distance_squared(&self, target_x: f64, target_y: f64, target_z: f64) -> f64 {
        let dx = self.x - target_x;
        let dy = self.y - target_y;
        let dz = self.z - target_z;
        dx * dx + dy * dy + dz * dz
    }

    #[inline(always)]
    pub fn speed(&self) -> f64 {
        (self.vx * self.vx + self.vy * self.vy + self.vz * self.vz).sqrt()
    }
}

/// Contiguous heap buffer holding thousands of tracks with zero reallocation.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct TrackBatch {
    pub tracks: Vec<Track>,
}

impl TrackBatch {
    pub fn new() -> Self {
        Self {
            tracks: Vec::with_capacity(4096),
        }
    }

    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            tracks: Vec::with_capacity(capacity),
        }
    }

    #[inline(always)]
    pub fn push(&mut self, track: Track) {
        self.tracks.push(track);
    }

    #[inline(always)]
    pub fn len(&self) -> usize {
        self.tracks.len()
    }

    #[inline(always)]
    pub fn is_empty(&self) -> bool {
        self.tracks.is_empty()
    }

    #[inline(always)]
    pub fn clear(&mut self) {
        self.tracks.clear();
    }

    pub fn as_slice(&self) -> &[Track] {
        &self.tracks
    }

    pub fn as_mut_slice(&mut self) -> &mut [Track] {
        &mut self.tracks
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_track_properties() {
        let t = Track::new(1, 10.0, 20.0, 30.0, 3.0, 4.0, 0.0, 0.5, 3, 100);
        assert_eq!(t.id, 1);
        assert_eq!(t.speed(), 5.0);
        assert_eq!(t.distance_squared(10.0, 20.0, 30.0), 0.0);
    }

    #[test]
    fn test_track_batch() {
        let mut b = TrackBatch::new();
        assert!(b.is_empty());
        b.push(Track::new(1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0));
        assert_eq!(b.len(), 1);
        assert!(!b.is_empty());
        b.clear();
        assert_eq!(b.len(), 0);
    }
}

