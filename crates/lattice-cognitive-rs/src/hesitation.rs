use crate::track::{Track, TrackBatch};

/// Evaluator for Operator Hesitation and Cognitive Saturation.
#[derive(Debug, Clone)]
pub struct HesitationEngine {
    pub max_capacity: f64,
    pub w_tracks: f64,
    pub w_ambiguity: f64,
    pub w_oscillation: f64,
    pub w_pending: f64,
}

impl Default for HesitationEngine {
    fn default() -> Self {
        Self {
            max_capacity: 12.0,
            w_tracks: 0.35,
            w_ambiguity: 0.30,
            w_oscillation: 0.20,
            w_pending: 0.15,
        }
    }
}

impl HesitationEngine {
    pub fn new(max_capacity: f64) -> Self {
        Self {
            max_capacity: if max_capacity > 0.0 { max_capacity } else { 12.0 },
            ..Default::default()
        }
    }

    /// Computes the Decision Hesitation Index (DHI) vectorized over an entire batch.
    pub fn calculate_dhi(
        &self,
        batch: &TrackBatch,
        oscillation_rate: f64,
        pending_tasks: usize,
    ) -> (f64, bool) {
        let count = batch.len() as f64;
        if count == 0.0 {
            return (0.0, false);
        }

        let mut sum_ambiguity = 0.0;
        for track in batch.as_slice() {
            sum_ambiguity += track.ambiguity;
        }
        let mean_ambiguity = sum_ambiguity / count;

        let track_pressure = (1.0 + count / self.max_capacity).log2().clamp(0.0, 1.0);
        let ambiguity_term = mean_ambiguity.powf(1.5).clamp(0.0, 1.0);
        let oscillation_term = oscillation_rate.clamp(0.0, 1.0);
        let pending_term = ((pending_tasks as f64) / count).clamp(0.0, 1.0);

        let dhi = (self.w_tracks * track_pressure
            + self.w_ambiguity * ambiguity_term
            + self.w_oscillation * oscillation_term
            + self.w_pending * pending_term)
            .clamp(0.0, 1.0);

        let is_bottleneck = dhi > 0.70;
        (dhi, is_bottleneck)
    }

    /// Cognitive Resilience Architecture (CRA): Dynamic Decoy Clustering.
    /// Aggregates contiguous decoy swarms within `cluster_radius_m` into centroid cluster tracks,
    /// collapsing visual cognitive noise for the human operator.
    pub fn cluster_decoys(
        &self,
        input: &TrackBatch,
        output: &mut TrackBatch,
        cluster_radius_m: f64,
    ) -> usize {
        output.clear();
        let radius_sq = cluster_radius_m * cluster_radius_m;

        let mut decoys: Vec<Track> = Vec::new();

        // Separate non-decoys directly into output, collect decoys for clustering
        for track in input.as_slice() {
            if track.classification == 4 {
                decoys.push(*track);
            } else {
                output.push(*track);
            }
        }

        let mut clusters_formed = 0;
        let mut visited = vec![false; decoys.len()];

        for i in 0..decoys.len() {
            if visited[i] {
                continue;
            }
            visited[i] = true;

            let mut cluster_members = vec![decoys[i]];
            for j in (i + 1)..decoys.len() {
                if !visited[j] {
                    let d_sq = decoys[i].distance_squared(decoys[j].x, decoys[j].y, decoys[j].z);
                    if d_sq <= radius_sq {
                        visited[j] = true;
                        cluster_members.push(decoys[j]);
                    }
                }
            }

            if cluster_members.len() > 1 {
                clusters_formed += 1;
                // Calculate centroid
                let n = cluster_members.len() as f64;
                let (mut sum_x, mut sum_y, mut sum_z) = (0.0, 0.0, 0.0);
                let (mut sum_vx, mut sum_vy, mut sum_vz) = (0.0, 0.0, 0.0);
                let mut max_ambiguity = 0.0;

                for m in &cluster_members {
                    sum_x += m.x;
                    sum_y += m.y;
                    sum_z += m.z;
                    sum_vx += m.vx;
                    sum_vy += m.vy;
                    sum_vz += m.vz;
                    if m.ambiguity > max_ambiguity {
                        max_ambiguity = m.ambiguity;
                    }
                }

                // Add synthetic cluster track (Classification: DECOY=4, ambiguity lowered by clustering)
                output.push(Track::new(
                    900000 + (clusters_formed as u64),
                    sum_x / n,
                    sum_y / n,
                    sum_z / n,
                    sum_vx / n,
                    sum_vy / n,
                    sum_vz / n,
                    max_ambiguity * 0.4, // Ambiguity reduced by cluster aggregation
                    4,
                    cluster_members[0].timestamp_ms,
                ));
            } else {
                output.push(cluster_members[0]);
            }
        }

        clusters_formed
    }
}
