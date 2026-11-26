import pytest
from lattice_cognitive.engine.swarm_dispersion import DecoySwarmCluster
from lattice_cognitive.twin.schema import Classification


def test_decoy_swarm_dispersion_generation():
    cluster = DecoySwarmCluster(
        cluster_id="swarm-alpha-09",
        centroid_lat=34.05,
        centroid_lon=-118.25,
        base_altitude_m=2800.0,
        num_decoys=8,
        dispersion_radius_m=1500.0,
    )

    tracks = cluster.generate_dispersed_tracks()
    assert len(tracks) == 8

    # Ensure coordinates are dispersed within expected bounds
    for t in tracks:
        assert abs(t.latitude - 34.05) < 0.05
        assert abs(t.longitude - (-118.25)) < 0.05
        assert 2600.0 <= t.altitude_m <= 3000.0
        assert t.classification in (Classification.DECOY, Classification.SUSPECT)
