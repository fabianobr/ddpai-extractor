import json
import os
import sys

# Insert the current directory (worktree) at the beginning of path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_dir = os.path.dirname(current_dir)
sys.path.insert(0, repo_dir)


def test_trips_json_contains_idle_segments():
    """Test that generated trips.json contains idle_segments."""
    json_path = 'data/trips.json'

    if not os.path.exists(json_path):
        print(f"⊘ Skipping: {json_path} not found (may not have run build yet)")
        return

    with open(json_path) as f:
        data = json.load(f)

    # Verify structure
    assert 'trips' in data, "Missing 'trips' key in JSON"
    assert isinstance(data['trips'], list), "'trips' should be a list"

    # Each trip should have idle_segments field
    for trip in data['trips']:
        assert 'idle_segments' in trip, f"Trip {trip.get('id')} missing idle_segments"
        assert isinstance(trip['idle_segments'], list), "idle_segments should be a list"

        # Each idle segment should have required fields
        for idle_seg in trip['idle_segments']:
            assert 'start_index' in idle_seg, "Missing start_index"
            assert 'end_index' in idle_seg, "Missing end_index"
            assert 'duration_s' in idle_seg, "Missing duration_s"
            assert 'distance_km' in idle_seg, "Missing distance_km"

            # Validate data types
            assert isinstance(idle_seg['start_index'], int), "start_index should be int"
            assert isinstance(idle_seg['end_index'], int), "end_index should be int"
            assert isinstance(idle_seg['duration_s'], (int, float)), "duration_s should be numeric"
            assert isinstance(idle_seg['distance_km'], (int, float)), "distance_km should be numeric"

    print("✅ test_trips_json_contains_idle_segments PASSED")


def test_idle_segments_respect_thresholds():
    """Verify all idle segments meet duration threshold."""
    from src.extraction.build_database import IDLE_DURATION_THRESHOLD

    json_path = 'data/trips.json'
    if not os.path.exists(json_path):
        print(f"⊘ Skipping: {json_path} not found")
        return

    with open(json_path) as f:
        data = json.load(f)

    for trip in data['trips']:
        for seg in trip.get('idle_segments', []):
            assert seg['duration_s'] >= IDLE_DURATION_THRESHOLD, \
                f"Idle segment duration {seg['duration_s']}s < threshold {IDLE_DURATION_THRESHOLD}s"

    print("✅ test_idle_segments_respect_thresholds PASSED")


# Run tests when executed directly
if __name__ == '__main__':
    try:
        test_trips_json_contains_idle_segments()
        test_idle_segments_respect_thresholds()
        print("\n✅ All integration tests PASSED")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
