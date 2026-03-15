import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.extraction.build_database import detect_idle_segments, IDLE_SPEED_THRESHOLD, IDLE_DURATION_THRESHOLD


def test_detect_single_idle_segment():
    """Test detection of a single continuous idle period."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 10.0, 'timestamp': 60},
        {'speed_kmh': 10.0, 'timestamp': 120},
        {'speed_kmh': 0.0, 'timestamp': 180},
        {'speed_kmh': 0.0, 'timestamp': 240},
        {'speed_kmh': 0.0, 'timestamp': 300},
        {'speed_kmh': 0.0, 'timestamp': 360},
        {'speed_kmh': 0.0, 'timestamp': 420},
        {'speed_kmh': 0.0, 'timestamp': 480},
        {'speed_kmh': 15.0, 'timestamp': 540},
        {'speed_kmh': 15.0, 'timestamp': 600},
    ]
    idle_segments = detect_idle_segments(points)
    assert len(idle_segments) == 1
    assert idle_segments[0]['start_index'] == 3
    assert idle_segments[0]['end_index'] == 8
    assert idle_segments[0]['duration_s'] == 300


def test_no_idle_segments_when_speed_above_threshold():
    """Test that no idle segments are detected when speed stays above threshold."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 15.0, 'timestamp': 60},
        {'speed_kmh': 20.0, 'timestamp': 120},
        {'speed_kmh': 12.0, 'timestamp': 180},
    ]
    idle_segments = detect_idle_segments(points)
    assert len(idle_segments) == 0


def test_idle_period_too_short_ignored():
    """Test that idle periods shorter than threshold are ignored."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.0, 'timestamp': 60},
        {'speed_kmh': 0.0, 'timestamp': 120},
        {'speed_kmh': 10.0, 'timestamp': 180},
    ]
    idle_segments = detect_idle_segments(points)
    assert len(idle_segments) == 0


def test_multiple_idle_segments():
    """Test detection of multiple non-overlapping idle periods."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.0, 'timestamp': 60},
        {'speed_kmh': 0.0, 'timestamp': 120},
        {'speed_kmh': 0.0, 'timestamp': 180},
        {'speed_kmh': 0.0, 'timestamp': 240},
        {'speed_kmh': 0.0, 'timestamp': 300},
        {'speed_kmh': 0.0, 'timestamp': 360},
        {'speed_kmh': 0.0, 'timestamp': 420},
        {'speed_kmh': 10.0, 'timestamp': 480},
        {'speed_kmh': 20.0, 'timestamp': 540},
        {'speed_kmh': 0.0, 'timestamp': 600},
        {'speed_kmh': 0.0, 'timestamp': 660},
        {'speed_kmh': 0.0, 'timestamp': 720},
        {'speed_kmh': 0.0, 'timestamp': 780},
        {'speed_kmh': 0.0, 'timestamp': 840},
        {'speed_kmh': 0.0, 'timestamp': 900},
        {'speed_kmh': 15.0, 'timestamp': 960},
    ]
    idle_segments = detect_idle_segments(points)
    assert len(idle_segments) == 2
    assert idle_segments[0]['start_index'] == 1
    assert idle_segments[0]['end_index'] == 7
    assert idle_segments[1]['start_index'] == 10
    assert idle_segments[1]['end_index'] == 15


def test_idle_segment_with_custom_threshold():
    """Test idle detection with custom speed threshold."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.3, 'timestamp': 60},
        {'speed_kmh': 0.2, 'timestamp': 120},
        {'speed_kmh': 0.1, 'timestamp': 180},
        {'speed_kmh': 0.4, 'timestamp': 240},
        {'speed_kmh': 0.5, 'timestamp': 300},
        {'speed_kmh': 0.2, 'timestamp': 360},
        {'speed_kmh': 15.0, 'timestamp': 420},
    ]
    idle_segments = detect_idle_segments(points, speed_threshold=5.0)
    assert len(idle_segments) == 1
    assert idle_segments[0]['start_index'] == 1
    assert idle_segments[0]['end_index'] == 6


# Run tests when executed directly
if __name__ == '__main__':
    test_count = 0
    passed_count = 0
    failed_count = 0

    tests = [
        test_detect_single_idle_segment,
        test_no_idle_segments_when_speed_above_threshold,
        test_idle_period_too_short_ignored,
        test_multiple_idle_segments,
        test_idle_segment_with_custom_threshold,
    ]

    for test_func in tests:
        test_count += 1
        try:
            test_func()
            passed_count += 1
            print(f"✅ {test_func.__name__}")
        except AssertionError as e:
            failed_count += 1
            print(f"❌ {test_func.__name__}: {e}")
        except Exception as e:
            failed_count += 1
            print(f"❌ {test_func.__name__}: ERROR - {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed_count} passed, {failed_count} failed out of {test_count} tests")
    print(f"{'='*60}")

    if failed_count > 0:
        sys.exit(1)
