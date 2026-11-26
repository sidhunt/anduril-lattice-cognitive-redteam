pub mod filter;
pub mod hesitation;
pub mod mavlink_sitl;
pub mod track;

use pyo3::prelude::*;
use std::time::Instant;

use filter::{FastCognitiveFilter, RadarSector};
use hesitation::HesitationEngine;
use mavlink_sitl::MavlinkSitlEngine;
use track::{Track, TrackBatch};

/// Python wrapper for high-throughput Track.
#[pyclass(name = "Track")]
#[derive(Clone)]
pub struct PyTrack {
    #[pyo3(get, set)]
    pub id: u64,
    #[pyo3(get, set)]
    pub x: f64,
    #[pyo3(get, set)]
    pub y: f64,
    #[pyo3(get, set)]
    pub z: f64,
    #[pyo3(get, set)]
    pub vx: f64,
    #[pyo3(get, set)]
    pub vy: f64,
    #[pyo3(get, set)]
    pub vz: f64,
    #[pyo3(get, set)]
    pub ambiguity: f64,
    #[pyo3(get, set)]
    pub classification: u8,
    #[pyo3(get, set)]
    pub timestamp_ms: u64,
}

#[pymethods]
impl PyTrack {
    #[new]
    #[pyo3(signature = (id, x, y, z, vx=0.0, vy=0.0, vz=0.0, ambiguity=0.0, classification=1, timestamp_ms=0))]
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
            ambiguity,
            classification,
            timestamp_ms,
        }
    }

    pub fn speed(&self) -> f64 {
        (self.vx * self.vx + self.vy * self.vy + self.vz * self.vz).sqrt()
    }

    pub fn to_dict(&self, py: Python) -> PyResult<PyObject> {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("id", self.id)?;
        dict.set_item("x", self.x)?;
        dict.set_item("y", self.y)?;
        dict.set_item("z", self.z)?;
        dict.set_item("vx", self.vx)?;
        dict.set_item("vy", self.vy)?;
        dict.set_item("vz", self.vz)?;
        dict.set_item("ambiguity", self.ambiguity)?;
        dict.set_item("classification", self.classification)?;
        dict.set_item("timestamp_ms", self.timestamp_ms)?;
        Ok(dict.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "Track(id={}, pos=[{:.1}, {:.1}, {:.1}], class={}, amb={:.2})",
            self.id, self.x, self.y, self.z, self.classification, self.ambiguity
        )
    }
}

impl From<Track> for PyTrack {
    fn from(t: Track) -> Self {
        Self {
            id: t.id,
            x: t.x,
            y: t.y,
            z: t.z,
            vx: t.vx,
            vy: t.vy,
            vz: t.vz,
            ambiguity: t.ambiguity,
            classification: t.classification,
            timestamp_ms: t.timestamp_ms,
        }
    }
}

impl From<PyTrack> for Track {
    fn from(pt: PyTrack) -> Self {
        Track::new(
            pt.id,
            pt.x,
            pt.y,
            pt.z,
            pt.vx,
            pt.vy,
            pt.vz,
            pt.ambiguity,
            pt.classification,
            pt.timestamp_ms,
        )
    }
}

/// Contiguous Track buffer for high-throughput batch operations.
#[pyclass(name = "TrackBatch")]
#[derive(Clone, Default)]
pub struct PyTrackBatch {
    pub inner: TrackBatch,
}

#[pymethods]
impl PyTrackBatch {
    #[new]
    #[pyo3(signature = (capacity=4096))]
    pub fn new(capacity: usize) -> Self {
        Self {
            inner: TrackBatch::with_capacity(capacity),
        }
    }

    pub fn push(&mut self, track: PyTrack) {
        self.inner.push(track.into());
    }

    pub fn len(&self) -> usize {
        self.inner.len()
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }

    pub fn __getitem__(&self, index: usize) -> PyResult<PyTrack> {
        self.inner
            .as_slice()
            .get(index)
            .copied()
            .map(PyTrack::from)
            .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("Index out of bounds"))
    }

    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    pub fn clear(&mut self) {
        self.inner.clear();
    }

    pub fn get(&self, index: usize) -> Option<PyTrack> {
        self.inner.as_slice().get(index).copied().map(PyTrack::from)
    }

    /// Generates N synthetic tracks for benchmarking and simulation.
    pub fn populate_synthetic(&mut self, count: usize, radius_m: f64, ambiguity: f64) {
        for i in 0..count {
            let angle = (i as f64) * 0.1;
            let dist = radius_m * (0.2 + 0.8 * ((i % 100) as f64 / 100.0));
            let x = dist * angle.cos();
            let y = dist * angle.sin();
            let z = 50.0 + ((i % 20) as f64) * 20.0;
            let class = if i % 4 == 0 { 4 } else { 1 }; // Decoy or Unknown

            self.inner.push(Track::new(
                i as u64,
                x,
                y,
                z,
                -15.0 * angle.sin(),
                15.0 * angle.cos(),
                0.0,
                ambiguity,
                class,
                0,
            ));
        }
    }

    pub fn to_list(&self) -> Vec<PyTrack> {
        self.inner.as_slice().iter().copied().map(PyTrack::from).collect()
    }
}

/// Zero-copy C2 radar coverage filter.
#[pyclass(name = "FastCognitiveFilter")]
#[derive(Default)]
pub struct PyFastCognitiveFilter {
    inner: FastCognitiveFilter,
}

#[pymethods]
impl PyFastCognitiveFilter {
    #[new]
    pub fn new() -> Self {
        Self {
            inner: FastCognitiveFilter::new(),
        }
    }

    pub fn add_sector(
        &mut self,
        origin_x: f64,
        origin_y: f64,
        origin_z: f64,
        min_range: f64,
        max_range: f64,
        min_altitude: f64,
        max_altitude: f64,
    ) {
        self.inner.add_sector(RadarSector::new(
            origin_x,
            origin_y,
            origin_z,
            min_range,
            max_range,
            min_altitude,
            max_altitude,
        ));
    }

    pub fn filter_batch(&self, input: &PyTrackBatch) -> PyTrackBatch {
        let mut output = TrackBatch::with_capacity(input.len());
        self.inner.filter_in_coverage(&input.inner, &mut output);
        PyTrackBatch { inner: output }
    }

    pub fn compute_metrics(&self, batch: &PyTrackBatch) -> (usize, f64, usize) {
        self.inner.compute_metrics(&batch.inner)
    }
}

/// Vectorized Operator Hesitation Engine & Cognitive Resilience Architecture.
#[pyclass(name = "HesitationEngine")]
pub struct PyHesitationEngine {
    inner: HesitationEngine,
}

#[pymethods]
impl PyHesitationEngine {
    #[new]
    #[pyo3(signature = (max_capacity=12.0))]
    pub fn new(max_capacity: f64) -> Self {
        Self {
            inner: HesitationEngine::new(max_capacity),
        }
    }

    pub fn calculate_dhi(
        &self,
        batch: &PyTrackBatch,
        oscillation_rate: f64,
        pending_tasks: usize,
    ) -> (f64, bool) {
        self.inner.calculate_dhi(&batch.inner, oscillation_rate, pending_tasks)
    }

    pub fn cluster_decoys(
        &self,
        input: &PyTrackBatch,
        cluster_radius_m: f64,
    ) -> (PyTrackBatch, usize) {
        let mut output = TrackBatch::with_capacity(input.len());
        let clusters = self.inner.cluster_decoys(&input.inner, &mut output, cluster_radius_m);
        (PyTrackBatch { inner: output }, clusters)
    }
}

/// MAVLink SITL Telemetry Adapter for virtual defense simulations.
#[pyclass(name = "MavlinkSitlEngine")]
pub struct PyMavlinkSitlEngine {
    inner: MavlinkSitlEngine,
}

#[pymethods]
impl PyMavlinkSitlEngine {
    #[new]
    #[pyo3(signature = (origin_lat=33.5, origin_lon=-116.5))]
    pub fn new(origin_lat: f64, origin_lon: f64) -> Self {
        Self {
            inner: MavlinkSitlEngine::new(origin_lat, origin_lon),
        }
    }

    pub fn parse_packets(&self, raw_bytes: &[u8]) -> (PyTrackBatch, usize) {
        let mut batch = TrackBatch::with_capacity(64);
        let parsed = self.inner.parse_packets(raw_bytes, &mut batch);
        (PyTrackBatch { inner: batch }, parsed)
    }

    pub fn generate_synthetic_sitl_swarm(
        &self,
        num_drones: usize,
        elapsed_s: f64,
        feint_radius_m: f64,
    ) -> Vec<u8> {
        self.inner.generate_synthetic_sitl_swarm(num_drones, elapsed_s, feint_radius_m)
    }
}

/// Benchmarks track processing throughput in Rust. Returns tracks processed per second.
#[pyfunction]
pub fn benchmark_throughput(num_tracks: usize) -> f64 {
    let mut batch = TrackBatch::with_capacity(num_tracks);
    for i in 0..num_tracks {
        batch.push(Track::new(
            i as u64,
            (i as f64) * 2.0,
            (i as f64) * 3.0,
            100.0,
            10.0,
            10.0,
            0.0,
            0.5,
            1,
            0,
        ));
    }

    let mut filter = FastCognitiveFilter::new();
    filter.add_sector(RadarSector::new(0.0, 0.0, 0.0, 100.0, 50000.0, 0.0, 5000.0));

    let engine = HesitationEngine::new(12.0);
    let mut out_batch = TrackBatch::with_capacity(num_tracks);

    let start = Instant::now();
    filter.filter_in_coverage(&batch, &mut out_batch);
    let _ = engine.calculate_dhi(&out_batch, 0.2, 5);
    let duration = start.elapsed().as_secs_f64();

    if duration > 0.0 {
        (num_tracks as f64) / duration
    } else {
        1_000_000_000.0
    }
}

/// PyO3 Module definition for lattice_cognitive_rs.
#[pymodule]
fn lattice_cognitive_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyTrack>()?;
    m.add_class::<PyTrackBatch>()?;
    m.add_class::<PyFastCognitiveFilter>()?;
    m.add_class::<PyHesitationEngine>()?;
    m.add_class::<PyMavlinkSitlEngine>()?;
    m.add_function(wrap_pyfunction!(benchmark_throughput, m)?)?;
    Ok(())
}
