use crate::track::{Track, TrackBatch};

/// Radar sensor coverage sector.
#[derive(Debug, Clone)]
pub struct RadarSector {
    pub origin_x: f64,
    pub origin_y: f64,
    pub origin_z: f64,
    pub min_range_sq: f64,
    pub max_range_sq: f64,
    pub min_altitude: f64,
    pub max_altitude: f64,
}

impl RadarSector {
    pub fn new(
        origin_x: f64,
        origin_y: f64,
        origin_z: f64,
        min_range: f64,
        max_range: f64,
        min_altitude: f64,
        max_altitude: f64,
    ) -> Self {
        Self {
            origin_x,
            origin_y,
            origin_z,
            min_range_sq: min_range * min_range,
            max_range_sq: max_range * max_range,
            min_altitude,
            max_altitude,
        }
    }

    #[inline(always)]
    pub fn contains(&self, track: &Track) -> bool {
        if track.z < self.min_altitude || track.z > self.max_altitude {
            return false;
        }
        let dist_sq = track.distance_squared(self.origin_x, self.origin_y, self.origin_z);
        dist_sq >= self.min_range_sq && dist_sq <= self.max_range_sq
    }
}

/// Zero-copy C2 Track Filter executing at gigahertz throughput.
#[derive(Debug, Clone, Default)]
pub struct FastCognitiveFilter {
    pub sectors: Vec<RadarSector>,
}

impl FastCognitiveFilter {
    pub fn new() -> Self {
        Self {
            sectors: Vec::new(),
        }
    }

    pub fn add_sector(&mut self, sector: RadarSector) {
        self.sectors.push(sector);
    }

    /// Filters a batch of tracks against radar coverage in zero allocations.
    pub fn filter_in_coverage(&self, input: &TrackBatch, output: &mut TrackBatch) {
        output.clear();
        for track in input.as_slice() {
            let in_coverage = if self.sectors.is_empty() {
                true
            } else {
                self.sectors.iter().any(|s| s.contains(track))
            };

            if in_coverage {
                output.push(*track);
            }
        }
    }

    /// Computes summary statistics over an input batch without heap allocations.
    pub fn compute_metrics(&self, batch: &TrackBatch) -> (usize, f64, usize) {
        if batch.is_empty() {
            return (0, 0.0, 0);
        }

        let mut sum_ambiguity = 0.0;
        let mut decoy_count = 0;

        for track in batch.as_slice() {
            sum_ambiguity += track.ambiguity;
            if track.classification == 4 {
                // 4 == DECOY
                decoy_count += 1;
            }
        }

        let mean_ambiguity = sum_ambiguity / (batch.len() as f64);
        (batch.len(), mean_ambiguity, decoy_count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_radar_sector_and_filter() {
        let mut filter = FastCognitiveFilter::new();
        filter.add_sector(RadarSector::new(0.0, 0.0, 0.0, 500.0, 2000.0, 0.0, 1000.0));

        let mut input = TrackBatch::new();
        input.push(Track::new(1, 1000.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.2, 1, 0));
        input.push(Track::new(2, 5000.0, 0.0, 500.0, 0.0, 0.0, 0.0, 0.2, 1, 0));

        let mut output = TrackBatch::new();
        filter.filter_in_coverage(&input, &mut output);
        assert_eq!(output.len(), 1);
        assert_eq!(output.as_slice()[0].id, 1);
    }
}

