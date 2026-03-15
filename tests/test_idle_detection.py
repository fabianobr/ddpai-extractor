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
        {'speed_kmh': 15.0, 'timestamp': 900},
    ]
    idle_segments = detect_idle_segments(points)
    assert len(idle_segments) == 2
    assert idle_segments[0]['start_index'] == 1
    assert idle_segments[0]['end_index'] == 7
    assert idle_segments[1]['start_index'] == 10
    assert idle_segments[1]['end_index'] == 14


def test_idle_segment_with_custom_threshold():
    """Test idle detection with custom speed threshold."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.3, 'timestamp': 60},
        {'speed_kmh': 0.2, 'timestamp': 120},
        {'speed_kmh': 0.1, 'timestamp': 180},
        {'speed_kmh': 0.4, 'timestamp': 240},
        {'speed_kmh': 0.5, 'timestamp': 300},
        {'speed_kmh': 15.0, 'timestamp': 360},
    ]
    idle_segments = detect_idle_segments(points, speed_threshold=5.0)
    assert len(idle_segments) == 1
    assert idle_segments[0]['start_index'] == 1
    assert idle_segments[0]['end_index'] == 5
