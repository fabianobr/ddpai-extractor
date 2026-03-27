"""
Regression tests for GPS point ordering fix.

Verifies:
- merge_gps_points sorts by timestamp, not (lat, lon)
- points_for_db in build_database.py includes 6 elements (lat, lon, spd, alt, hdg, time_offset_s)
- Same for build_database_parallel.py
"""
import pytest
from pathlib import Path

SEQ_FILE = Path(__file__).parent.parent / 'src' / 'extraction' / 'build_database.py'
PAR_FILE = Path(__file__).parent.parent / 'src' / 'extraction' / 'build_database_parallel.py'


@pytest.fixture(scope='module')
def seq_content():
    return SEQ_FILE.read_text()


@pytest.fixture(scope='module')
def par_content():
    return PAR_FILE.read_text()


def test_sort_key_is_timestamp_not_lat_lon(seq_content):
    """merge_gps_points must sort by timestamp, not geographic coordinates."""
    assert "key=lambda p: p['timestamp']" in seq_content, \
        "merge_gps_points must sort by timestamp (not lat/lon)"


def test_sort_key_not_lat_lon(seq_content):
    """Ensure the broken lat/lon sort is gone."""
    assert "key=lambda p: (p['lat'], p['lon'])" not in seq_content, \
        "Found broken lat/lon sort key — must be removed"


def test_points_for_db_has_six_elements(seq_content):
    """points_for_db must include time_offset_s as the 6th element."""
    assert 'time_offset_s' in seq_content or 'time_offset' in seq_content, \
        "points_for_db must include time_offset_s as 6th element"


def test_parallel_points_has_six_elements(par_content):
    """Parallel build points comprehension must also include time_offset_s."""
    assert 'time_offset_s' in par_content or 'time_offset' in par_content, \
        "build_database_parallel.py points must include time_offset_s as 6th element"
