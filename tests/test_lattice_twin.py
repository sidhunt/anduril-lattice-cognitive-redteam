import pytest
from lattice_cognitive.twin.mock_sdk import MockLatticeTwin
from lattice_cognitive.twin.schema import TrackEntity, Classification, TaskType, TaskStatus


def test_lattice_twin_initialization():
    twin = MockLatticeTwin(airspace_name="Test-Sector")
    tracks = twin.list_tracks()
    # At least two friendly sentries
    assert len(tracks) >= 2
    friendly_callsigns = [t.callsign for t in tracks]
    assert any("ANVIL" in c for c in friendly_callsigns)
    assert any("GHOST" in c for c in friendly_callsigns)


def test_publish_and_update_track():
    twin = MockLatticeTwin()
    new_track = TrackEntity(
        entity_id="track-bogie-01",
        callsign="BOGIE-01",
        classification=Classification.UNKNOWN,
        latitude=34.1,
        longitude=-118.3,
        altitude_m=4200.0,
        speed_mps=280.0,
        heading_deg=180.0,
    )
    twin.publish_track(new_track)
    fetched = twin.get_track("track-bogie-01")
    assert fetched is not None
    assert fetched.callsign == "BOGIE-01"


def test_dispatch_and_approve_task():
    twin = MockLatticeTwin()
    task = twin.dispatch_task(
        task_type=TaskType.INTERCEPT,
        target_entity_id="track-bogie-01",
        assigned_asset_id="asset-anvil-01",
    )
    assert task.status == TaskStatus.PENDING_APPROVAL
    assert task.target_entity_id == "track-bogie-01"

    approved = twin.operator_approve_task(
        task_id=task.task_id,
        operator_id="OP-VIPER",
        simulated_hesitation_ms=2800.0,
    )
    assert approved.status == TaskStatus.APPROVED
    assert approved.latency_ms == 2800.0
    assert approved.operator_id == "OP-VIPER"
