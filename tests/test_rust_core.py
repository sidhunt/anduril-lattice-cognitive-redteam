import pytest

try:
    import lattice_cognitive_rs as lrs
    RUST_CORE_AVAILABLE = True
except ImportError:
    lrs = None
    RUST_CORE_AVAILABLE = False


@pytest.mark.skipif(not RUST_CORE_AVAILABLE, reason="Rust core (lattice_cognitive_rs) not built")
def test_rust_track_creation_and_properties():
    t = lrs.Track(
        id=42,
        x=100.0,
        y=200.0,
        z=300.0,
        vx=10.0,
        vy=-15.0,
        vz=0.0,
        ambiguity=0.35,
        classification=3, # HOSTILE
        timestamp_ms=1000,
    )
    assert t.id == 42
    assert t.x == 100.0
    assert t.classification == 3
    assert t.ambiguity == 0.35
    assert abs(t.speed() - ((10.0**2 + (-15.0)**2) ** 0.5)) < 1e-4

    d = t.to_dict()
    assert d["id"] == 42
    assert d["classification"] == 3


@pytest.mark.skipif(not RUST_CORE_AVAILABLE, reason="Rust core (lattice_cognitive_rs) not built")
def test_rust_track_batch_and_throughput():
    batch = lrs.TrackBatch(1000)
    assert len(batch) == 0

    batch.populate_synthetic(500, 8000.0, 0.4)
    assert len(batch) == 500

    first = batch[0]
    assert first is not None
    assert first.id == 0

    # Benchmark throughput verification (> 1,000,000 tracks/sec)
    tp = lrs.benchmark_throughput(50000)
    assert tp > 1_000_000.0, f"Expected >1M tracks/sec, got {tp}"


@pytest.mark.skipif(not RUST_CORE_AVAILABLE, reason="Rust core (lattice_cognitive_rs) not built")
def test_rust_fast_cognitive_filter():
    filter_engine = lrs.FastCognitiveFilter()
    # Add sector covering 1000m to 5000m radius, 0-2000m altitude
    filter_engine.add_sector(0.0, 0.0, 0.0, 1000.0, 5000.0, 0.0, 2000.0)

    batch = lrs.TrackBatch(10)
    # Track inside coverage (dist = 2000m)
    batch.push(lrs.Track(1, 2000.0, 0.0, 500.0))
    # Track outside coverage (dist = 10000m)
    batch.push(lrs.Track(2, 10000.0, 0.0, 500.0))
    # Track out of altitude (z = 4000m)
    batch.push(lrs.Track(3, 2000.0, 0.0, 4000.0))

    filtered = filter_engine.filter_batch(batch)
    assert len(filtered) == 1
    assert filtered[0].id == 1


@pytest.mark.skipif(not RUST_CORE_AVAILABLE, reason="Rust core (lattice_cognitive_rs) not built")
def test_rust_vectorized_hesitation_and_cra_clustering():
    engine = lrs.HesitationEngine(12.0)

    # 1. Low load batch
    batch_low = lrs.TrackBatch(5)
    for i in range(4):
        batch_low.push(lrs.Track(i, 1000.0, 1000.0, 100.0, ambiguity=0.1, classification=1))
    dhi_low, bottleneck_low = engine.calculate_dhi(batch_low, 0.1, 0)
    assert dhi_low < 0.70
    assert not bottleneck_low

    # 2. Saturated swarm batch with decoys
    batch_sat = lrs.TrackBatch(60)
    # Add 40 tight decoys around (3000, 3000, 200)
    for i in range(40):
        offset = (i % 5) * 50.0
        batch_sat.push(lrs.Track(i, 3000.0 + offset, 3000.0 + offset, 200.0, ambiguity=0.8, classification=4))
    # Add 10 hostile tracks
    for i in range(40, 50):
        batch_sat.push(lrs.Track(i, 1500.0, 1500.0, 200.0, ambiguity=0.6, classification=3))

    dhi_sat, bottleneck_sat = engine.calculate_dhi(batch_sat, 0.8, 15)
    assert dhi_sat > 0.70
    assert bottleneck_sat

    # 3. Test CRA dynamic decoy clustering
    clustered, num_clusters = engine.cluster_decoys(batch_sat, 500.0)
    # The 40 decoys within 500m should be collapsed into clusters
    assert len(clustered) < len(batch_sat)
    assert num_clusters > 0

    # Verify DHI after CRA clustering
    dhi_post, bottleneck_post = engine.calculate_dhi(clustered, 0.3, 2)
    assert dhi_post < dhi_sat
