#!/usr/bin/env python3
"""
Merge multiple consecutive GPS trips into one continuous travel.
Handles all GPS data, videos, and recalculates statistics.
"""
import os
import tarfile
import glob
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import math

# Import shared functions
def parse_nmea_sentence(sentence):
    if not sentence.startswith('$'):
        return None
    if '*' in sentence:
        sentence = sentence[:sentence.index('*')]
    parts = sentence[1:].split(',')
    if len(parts) < 2:
        return None
    return {'type': parts[0], 'data': parts[1:]}

def dms_to_decimal(coord_str, direction):
    if not coord_str:
        return None
    try:
        if '.' in coord_str:
            dot_pos = coord_str.index('.')
            degrees = int(coord_str[:dot_pos-2])
            minutes = float(coord_str[dot_pos-2:])
        else:
            degrees = int(coord_str[:-7])
            minutes = float(coord_str[-7:])
        decimal = degrees + minutes / 60.0
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal
    except (ValueError, IndexError):
        return None

def parse_rmc(data):
    if len(data) < 11:
        return None
    try:
        time_str = data[0]
        status = data[1]
        lat_str = data[2]
        lat_dir = data[3]
        lon_str = data[4]
        lon_dir = data[5]
        if status != 'A' or not lat_str or not lon_str:
            return None
        lat = dms_to_decimal(lat_str, lat_dir)
        lon = dms_to_decimal(lon_str, lon_dir)
        if lat is None or lon is None:
            return None
        speed_knots = float(data[6]) if len(data) > 6 and data[6] else 0
        speed_kmh = speed_knots * 1.852
        heading = float(data[7]) if len(data) > 7 and data[7] else None
        return {
            'time': time_str,
            'lat': lat,
            'lon': lon,
            'speed_kmh': speed_kmh,
            'heading': heading
        }
    except (ValueError, IndexError):
        return None

def parse_gga(data):
    if len(data) < 12:
        return None
    try:
        time_str = data[0]
        num_sats = int(data[6]) if len(data) > 6 and data[6] else 0
        hdop = float(data[7]) if len(data) > 7 and data[7] else None
        altitude = float(data[8]) if len(data) > 8 and data[8] else 0
        return {
            'time': time_str,
            'altitude': altitude,
            'num_sats': num_sats,
            'hdop': hdop
        }
    except (ValueError, IndexError):
        return None

def parse_gps_file(tar_path, member_name):
    try:
        with tarfile.open(tar_path, 'r') as tar:
            try:
                f = tar.extractfile(member_name)
                if not f:
                    return None
                lines = f.read().decode('utf-8', errors='ignore').split('\n')
                camera_time = None
                if lines and lines[0].startswith('$GPSCAMTIME'):
                    camera_time = lines[0].split()[-1]
                rmc_by_time = {}
                gga_by_time = {}
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    parsed = parse_nmea_sentence(line)
                    if not parsed:
                        continue
                    if parsed['type'] in ['GPRMC', 'GNRMC']:
                        rmc = parse_rmc(parsed['data'])
                        if rmc:
                            rmc_by_time[rmc['time']] = rmc
                    elif parsed['type'] == 'GPGGA':
                        gga = parse_gga(parsed['data'])
                        if gga:
                            gga_by_time[gga['time']] = gga
                points = []
                for time_str, rmc in rmc_by_time.items():
                    gga = gga_by_time.get(time_str, {})
                    point = {
                        'lat': rmc['lat'],
                        'lon': rmc['lon'],
                        'speed_kmh': rmc['speed_kmh'],
                        'heading': rmc.get('heading'),
                        'altitude': gga.get('altitude', 0),
                        'num_sats': gga.get('num_sats', 0),
                        'hdop': gga.get('hdop'),
                        'time': time_str,
                        'camera_time': camera_time
                    }
                    points.append(point)
                return points if points else None
            except KeyError:
                return None
    except Exception:
        return None

def parse_single_tar_archive(tar_path):
    """Parse single TAR archive and return trip data."""
    archive_name = os.path.basename(tar_path)
    timestamp_str = archive_name.split('_')[0]
    try:
        dt_utc = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    except:
        return None

    # Convert to UTC-3 (São Paulo/Florianópolis)
    dt_local = dt_utc - timedelta(hours=3)

    all_points = []
    try:
        with tarfile.open(tar_path, 'r') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.gpx'):
                    points = parse_gps_file(tar_path, member.name)
                    if points:
                        all_points.extend(points)
    except Exception:
        return None

    if not all_points:
        return None

    points_with_dt = []
    for p in all_points:
        try:
            time_parts = p['time'].split('.')
            hms = time_parts[0]
            h = int(hms[0:2])
            m = int(hms[2:4])
            s = int(hms[4:6])
            dt = dt_local.replace(hour=h, minute=m, second=s, microsecond=0)
            p['datetime'] = dt
            p['timestamp'] = dt.isoformat()
            points_with_dt.append(p)
        except:
            pass

    if not points_with_dt:
        return None

    points_with_dt.sort(key=lambda p: p['datetime'])

    return {
        'id': timestamp_str,
        'date': dt_local.strftime('%Y-%m-%d'),
        'label': dt_local.strftime('%b %d %H:%M'),
        'start': points_with_dt[0]['timestamp'],
        'end': points_with_dt[-1]['timestamp'],
        'points': points_with_dt,
        'tar_path': tar_path
    }

def find_videos_for_trip(trip_id):
    """Find video files for a trip."""
    video_dir_rear = '/Users/fabianosilva/dashcam/DCIM/200video/rear'
    video_dir_front = '/Users/fabianosilva/dashcam/DCIM/200video/front'

    videos = {'rear': [], 'front': []}

    rear_pattern = os.path.join(video_dir_rear, f'{trip_id}*.mp4')
    for video_path in glob.glob(rear_pattern):
        videos['rear'].append(video_path)

    front_pattern = os.path.join(video_dir_front, f'{trip_id}*.mp4')
    for video_path in glob.glob(front_pattern):
        videos['front'].append(video_path)

    return videos

def haversine(p1, p2):
    """Calculate distance in meters."""
    R = 6371000
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def compute_trip_stats(points):
    """Compute trip statistics."""
    if len(points) < 2:
        return {'distance_km': 0, 'duration_min': 0, 'max_speed': 0, 'avg_speed': 0}

    total_distance = 0
    for i in range(len(points) - 1):
        p1 = (points[i]['lat'], points[i]['lon'])
        p2 = (points[i+1]['lat'], points[i+1]['lon'])
        total_distance += haversine(p1, p2)

    distance_km = total_distance / 1000
    start_dt = points[0]['datetime']
    end_dt = points[-1]['datetime']
    duration_min = (end_dt - start_dt).total_seconds() / 60

    speeds = [p['speed_kmh'] for p in points]
    max_speed = max(speeds) if speeds else 0
    avg_speed = sum(speeds) / len(speeds) if speeds else 0

    return {
        'distance_km': round(distance_km, 2),
        'duration_min': round(duration_min, 1),
        'max_speed': round(max_speed, 1),
        'avg_speed': round(avg_speed, 1)
    }

def merge_trips(tar_dir, trip_indices, output_file, dashcam_root):
    """Merge multiple consecutive trips into one."""

    tar_files = sorted(glob.glob(os.path.join(tar_dir, '*.git')))

    print(f"\nMerging trips: {trip_indices}")
    print("=" * 70)

    # Parse all trips in the range
    all_merged_points = []
    all_video_ids = set()
    first_trip_data = None

    for idx in trip_indices:
        if idx >= len(tar_files):
            continue

        tar_path = tar_files[idx]
        basename = os.path.basename(tar_path)
        print(f"Processing trip {idx}: {basename}...", end=' ', flush=True)

        trip = parse_single_tar_archive(tar_path)
        if trip:
            all_merged_points.extend(trip['points'])
            all_video_ids.add(trip['id'])
            if not first_trip_data:
                first_trip_data = trip
            print(f"✓ {len(trip['points'])} points")
        else:
            print("✗")

    if not all_merged_points or not first_trip_data:
        print("Error: Could not extract points for merge")
        return

    # Sort all points chronologically
    all_merged_points.sort(key=lambda p: p['datetime'])

    # Create merged trip ID
    start_dt = all_merged_points[0]['datetime']
    end_dt = all_merged_points[-1]['datetime']
    merged_id = f"{start_dt.strftime('%Y%m%d%H%M%S')}-{end_dt.strftime('%H%M%S')}"

    # Collect all videos
    all_videos = {'rear': [], 'front': []}
    for video_id in all_video_ids:
        videos = find_videos_for_trip(video_id)
        all_videos['rear'].extend(videos['rear'])
        all_videos['front'].extend(videos['front'])

    # Sort videos by filename (timestamp)
    all_videos['rear'].sort()
    all_videos['front'].sort()

    # Create merged trip object
    merged_trip = {
        'id': merged_id,
        'is_merged': True,
        'source_trips': list(all_video_ids),
        'trip_indices': trip_indices,
        'date': start_dt.strftime('%Y-%m-%d'),
        'label': f"{start_dt.strftime('%b %d %H:%M')} - {end_dt.strftime('%H:%M')} (MERGED)",
        'start': all_merged_points[0]['timestamp'],
        'end': all_merged_points[-1]['timestamp'],
        'points': all_merged_points,
        'videos': {
            'rear': [os.path.basename(v) for v in all_videos['rear']],
            'front': [os.path.basename(v) for v in all_videos['front']]
        }
    }

    # Compute stats
    stats = compute_trip_stats(all_merged_points)
    merged_trip.update(stats)

    # Simplify points for JSON
    merged_trip['points'] = [
        [
            round(p['lat'], 6),
            round(p['lon'], 6),
            round(p['speed_kmh'], 1),
            round(p['altitude'], 1) if p.get('altitude') else 0,
            round(p['heading'], 1) if p.get('heading') else 0
        ]
        for p in merged_trip['points']
    ]

    print("\n" + "=" * 70)
    print(f"✅ MERGED TRIP CREATED:")
    print(f"   ID: {merged_trip['id']}")
    print(f"   Date: {merged_trip['date']}")
    print(f"   Duration: {merged_trip['duration_min']} minutes")
    print(f"   Distance: {merged_trip['distance_km']} km")
    print(f"   Total points: {len(merged_trip['points'])}")
    print(f"   Videos linked: {len(all_videos['rear']) + len(all_videos['front'])} ({len(all_videos['rear'])} rear + {len(all_videos['front'])} front)")

    return merged_trip

def build_dashboard_with_merged(tar_dir, merged_trip, output_file, dashcam_root):
    """Build dashboard with merged trip at the beginning."""

    # Parse all individual trips
    tar_files = sorted(glob.glob(os.path.join(tar_dir, '*.git')))
    print(f"\nBuilding dashboard with {len(tar_files)} individual trips...")

    trips = []

    # Add merged trip first
    trips.append(merged_trip)

    for i, tar_path in enumerate(tar_files):
        basename = os.path.basename(tar_path)
        print(f"[{i+1}/{len(tar_files)}] {basename}...", end=' ', flush=True)

        trip = parse_single_tar_archive(tar_path)
        if trip:
            videos = find_videos_for_trip(trip['id'])
            trip['videos'] = {
                'rear': [os.path.basename(v) for v in videos['rear']],
                'front': [os.path.basename(v) for v in videos['front']]
            }

            stats = compute_trip_stats(trip['points'])
            trip.update(stats)

            trip['points'] = [
                [
                    round(p['lat'], 6),
                    round(p['lon'], 6),
                    round(p['speed_kmh'], 1),
                    round(p['altitude'], 1) if p.get('altitude') else 0,
                    round(p['heading'], 1) if p.get('heading') else 0
                ]
                for p in trip['points']
            ]

            trip['is_merged'] = False
            trips.append(trip)
            video_count = len(trip['videos']['rear']) + len(trip['videos']['front'])
            print(f"✓")
        else:
            print("✗")

    print(f"\nTotal trips: {len(trips)} (1 merged + {len(trips)-1} individual)")
    total_points = sum(len(t['points']) for t in trips)
    print(f"Total points: {total_points}")
    total_videos = sum(len(t['videos']['rear']) + len(t['videos']['front']) for t in trips)
    print(f"Total videos: {total_videos}")

    # Generate enhanced HTML
    html = generate_html(trips, dashcam_root)

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"\n✅ Generated: {output_file}")

def generate_html(trips, dashcam_root):
    """Generate HTML dashboard with merged trip highlighted."""
    trips_json = json.dumps(trips)

    day_colors = {
        '2026-03-05': '#FF6B6B',
        '2026-03-06': '#4ECDC4',
        '2026-03-07': '#95E1D3',
        '2026-03-08': '#FFA07A',
    }

    trips_by_date = defaultdict(list)
    for trip in trips:
        trips_by_date[trip['date']].append(trip)

    trip_list_html = ""
    for date in sorted(trips_by_date.keys()):
        trip_list_html += f'<div class="date-group"><strong>{date}</strong>\n'
        for trip in trips_by_date[date]:
            video_count = len(trip['videos']['rear']) + len(trip['videos']['front'])
            merged_badge = ' 🔗 MERGED' if trip.get('is_merged') else ''
            trip_list_html += f'''
    <div class="trip-item{' merged-trip' if trip.get('is_merged') else ''}" data-id="{trip['id']}">
        <div class="trip-time">{trip['label']}{merged_badge}</div>
        <div class="trip-stats">
            {trip['distance_km']} km · {trip['duration_min']} min
        </div>
        <div class="trip-videos">{video_count} 🎬</div>
    </div>
'''
        trip_list_html += '</div>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DDpai Dashboard - GPS + Videos + Merged Trips</title>
    <link rel="icon" type="image/x-icon" href="./favicon.ico">
    <link rel="icon" type="image/png" href="./favicon.png">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
        }}

        .container {{
            display: flex;
            height: 100vh;
            flex-direction: column;
        }}

        .top {{
            display: flex;
            flex: 1;
            gap: 12px;
            padding: 12px;
            min-height: 0;
        }}

        .sidebar {{
            width: 300px;
            background: white;
            border-radius: 4px;
            overflow-y: auto;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
        }}

        .sidebar-header {{
            padding: 16px;
            background: #2c3e50;
            color: white;
            font-weight: 600;
            flex-shrink: 0;
            border-radius: 4px 4px 0 0;
        }}

        .sidebar-content {{
            padding: 12px;
            overflow-y: auto;
            flex: 1;
        }}

        .date-group {{
            margin-bottom: 12px;
        }}

        .date-group strong {{
            display: block;
            padding: 6px 4px;
            color: #666;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .trip-item {{
            padding: 10px;
            margin: 4px 0;
            background: #f8f8f8;
            border-left: 3px solid #ccc;
            cursor: pointer;
            border-radius: 3px;
            transition: all 0.2s;
        }}

        .trip-item:hover {{
            background: #eee;
            transform: translateX(4px);
        }}

        .trip-item.active {{
            background: #e3f2fd;
            border-left-color: #2196F3;
        }}

        .trip-item.merged-trip {{
            background: #fff9e6;
            border-left-color: #FF9800;
            border-left-width: 4px;
            font-weight: 500;
        }}

        .trip-item.merged-trip.active {{
            background: #ffe0b2;
            border-left-color: #FF6F00;
        }}

        .trip-time {{
            font-size: 12px;
            font-weight: 500;
            color: #2c3e50;
        }}

        .trip-stats {{
            font-size: 10px;
            color: #999;
            margin-top: 3px;
        }}

        .trip-videos {{
            font-size: 10px;
            color: #FF6B6B;
            margin-top: 2px;
            font-weight: 500;
        }}

        .map-container {{
            flex: 1;
            background: #f0f0f0;
            border-radius: 4px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        #map {{
            width: 100%;
            height: 100%;
        }}

        .charts {{
            width: 320px;
            background: white;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .chart-container {{
            flex: 1;
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
            position: relative;
            min-height: 0;
        }}

        .chart-container:last-child {{
            border-bottom: none;
        }}

        .chart-title {{
            font-size: 11px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }}

        .bottom {{
            background: white;
            border-radius: 4px 4px 0 0;
            box-shadow: 0 -2px 4px rgba(0,0,0,0.1);
            height: 280px;
            overflow-y: auto;
            overflow-x: hidden;
            margin: 0 12px 12px 12px;
            flex-shrink: 0;
        }}

        .video-player {{
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
            flex-shrink: 0;
        }}

        .video-player:last-child {{
            border-bottom: none;
        }}

        .video-label {{
            font-size: 11px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 6px;
            display: flex;
            gap: 6px;
            align-items: center;
        }}

        .video-label span {{
            background: #FF6B6B;
            color: white;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 9px;
        }}

        .video-player video {{
            width: 100%;
            height: auto;
            max-height: 120px;
            background: #000;
            border-radius: 3px;
            cursor: pointer;
            display: block;
        }}

        .video-info {{
            font-size: 9px;
            color: #999;
            margin-top: 4px;
            padding: 0 4px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .header {{
            padding: 12px;
            background: white;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}

        .header-title {{
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
        }}

        button {{
            padding: 6px 12px;
            background: #2196F3;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: background 0.2s;
        }}

        button:hover {{
            background: #1976D2;
        }}

        button.active {{
            background: #4CAF50;
        }}

        .controls {{
            display: flex;
            gap: 8px;
        }}

        .no-video {{
            color: #999;
            font-size: 11px;
            padding: 8px;
            text-align: center;
        }}

        .trip-note {{
            font-size: 9px;
            color: #FF9800;
            font-weight: 600;
            margin-top: 2px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title">🎬 DDpai Dashboard - GPS + Videos - Florianópolis (UTC-3)</div>
        <div class="controls">
            <button id="btn-routes">🛣️ Routes</button>
        </div>
    </div>

    <div class="container">
        <div class="top">
            <div class="sidebar">
                <div class="sidebar-header">📍 Trips (Merged + Individual)</div>
                <div class="sidebar-content">
                    {trip_list_html}
                </div>
            </div>

            <div class="map-container">
                <div id="map"></div>
            </div>

            <div class="charts">
                <div class="chart-container">
                    <div class="chart-title">Speed</div>
                    <canvas id="chart-speed"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">Altitude</div>
                    <canvas id="chart-altitude"></canvas>
                </div>
            </div>
        </div>

        <div class="bottom">
            <div id="video-container">
                <div class="no-video">Select a trip to view videos</div>
            </div>
        </div>
    </div>

    <script>
        // Embedded trip data
        const TRIPS = {trips_json};
        const DASHCAM_ROOT = '{dashcam_root}';

        let speedChart = null;
        let altitudeChart = null;
        let routeLayer = L.featureGroup();
        let selectedTripPolyline = null;
        let selectedTripId = null;

        // Color by day
        const dayColors = {json.dumps(day_colors)};

        // Initialize map
        const map = L.map('map').setView([-27.595, -48.548], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }}).addTo(map);

        function init() {{
            renderAllRoutes();
            attachTripClickHandlers();
            initCharts();
        }}

        function getDayColor(date) {{
            return dayColors[date] || '#999';
        }}

        function getRouteColor(trip) {{
            if (trip.is_merged) {{
                return '#FF9800';  // Orange for merged
            }}
            return getDayColor(trip.date);
        }}

        function renderAllRoutes() {{
            routeLayer.clearLayers();
            TRIPS.forEach(trip => {{
                const points = trip.points.map(p => [p[0], p[1]]);
                const color = getRouteColor(trip);
                const weight = trip.is_merged ? 3 : 2;
                const opacity = trip.is_merged ? 0.9 : 0.6;

                const polyline = L.polyline(points, {{
                    color: color,
                    weight: weight,
                    opacity: opacity
                }});

                let popupText = `<strong>${{trip.label}}</strong><br>`;
                if (trip.is_merged) {{
                    popupText += '<span style="color: #FF9800; font-weight: bold;">🔗 MERGED TRIP</span><br>';
                }}
                popupText += `Distance: ${{trip.distance_km}} km<br>Duration: ${{trip.duration_min}} min<br>Max speed: ${{trip.max_speed}} km/h<br>Videos: ${{trip.videos.rear.length + trip.videos.front.length}}`;

                polyline.bindPopup(popupText);
                routeLayer.addLayer(polyline);
            }});
            routeLayer.addTo(map);
        }}

        function selectTrip(tripId) {{
            selectedTripId = tripId;
            document.querySelectorAll('.trip-item').forEach(el => {{
                el.classList.remove('active');
            }});
            document.querySelector(`[data-id="${{tripId}}"]`)?.classList.add('active');

            if (selectedTripPolyline) {{
                routeLayer.removeLayer(selectedTripPolyline);
            }}

            const trip = TRIPS.find(t => t.id === tripId);
            if (trip) {{
                const points = trip.points.map(p => [p[0], p[1]]);
                const color = trip.is_merged ? '#FF9800' : '#FF1493';
                selectedTripPolyline = L.polyline(points, {{
                    color: color,
                    weight: 4,
                    opacity: 1.0
                }});
                selectedTripPolyline.addTo(map);
                const bounds = L.latLngBounds(points);
                map.fitBounds(bounds, {{padding: [50, 50]}});
                updateCharts(trip);
                renderVideos(trip);
            }}
        }}

        function updateCharts(trip) {{
            if (!speedChart || !altitudeChart) return;
            const speeds = trip.points.map(p => p[2]);
            const altitudes = trip.points.map(p => p[3]);
            const labels = trip.points.map((_, i) => i);
            speedChart.data.labels = labels;
            speedChart.data.datasets[0].data = speeds;
            speedChart.update();
            altitudeChart.data.labels = labels;
            altitudeChart.data.datasets[0].data = altitudes;
            altitudeChart.update();
        }}

        function renderVideos(trip) {{
            const container = document.getElementById('video-container');
            container.innerHTML = '';

            if (trip.videos.rear.length === 0 && trip.videos.front.length === 0) {{
                container.innerHTML = '<div class="no-video">No videos for this trip</div>';
                return;
            }}

            trip.videos.rear.forEach((videoName, idx) => {{
                // Use relative path for HTTP serving
                const videoPath = `./videos/200video/rear/${{videoName}}`;
                const div = document.createElement('div');
                div.className = 'video-player';
                div.innerHTML = `
                    <div class="video-label">
                        📹 Rear Camera
                        <span>${{idx + 1}}/${{trip.videos.rear.length}}</span>
                    </div>
                    <video controls style="width: 100%; height: auto;">
                        <source src="${{videoPath}}" type="video/mp4">
                        Your browser doesn't support HTML5 video.
                    </video>
                    <div class="video-info">${{videoName}}</div>
                `;
                container.appendChild(div);
            }});

            trip.videos.front.forEach((videoName, idx) => {{
                // Use relative path for HTTP serving
                const videoPath = `./videos/200video/front/${{videoName}}`;
                const div = document.createElement('div');
                div.className = 'video-player';
                div.innerHTML = `
                    <div class="video-label">
                        📹 Front Camera
                        <span>${{idx + 1}}/${{trip.videos.front.length}}</span>
                    </div>
                    <video controls style="width: 100%; height: auto;">
                        <source src="${{videoPath}}" type="video/mp4">
                        Your browser doesn't support HTML5 video.
                    </video>
                    <div class="video-info">${{videoName}}</div>
                `;
                container.appendChild(div);
            }});
        }}

        function initCharts() {{
            const ctx1 = document.getElementById('chart-speed').getContext('2d');
            speedChart = new Chart(ctx1, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Speed (km/h)',
                        data: [],
                        borderColor: '#FF6B6B',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0,
                        borderWidth: 1.5
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{legend: {{display: false}}}},
                    scales: {{
                        y: {{beginAtZero: true, max: 100}},
                        x: {{display: false}}
                    }}
                }}
            }});

            const ctx2 = document.getElementById('chart-altitude').getContext('2d');
            altitudeChart = new Chart(ctx2, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Altitude (m)',
                        data: [],
                        borderColor: '#4ECDC4',
                        backgroundColor: 'rgba(78, 205, 196, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0,
                        borderWidth: 1.5
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{legend: {{display: false}}}},
                    scales: {{x: {{display: false}}}}
                }}
            }});
        }}

        function attachTripClickHandlers() {{
            document.querySelectorAll('.trip-item').forEach(el => {{
                el.addEventListener('click', () => {{
                    selectTrip(el.dataset.id);
                }});
            }});
        }}

        // Control buttons
        document.getElementById('btn-routes').addEventListener('click', function() {{
            this.classList.toggle('active');
            if (this.classList.contains('active')) {{
                routeLayer.addTo(map);
            }} else {{
                map.removeLayer(routeLayer);
            }}
        }});

        // Initialize
        init();
        if (TRIPS.length > 0) {{
            selectTrip(TRIPS[0].id);
            document.getElementById('btn-routes').click();
        }}
    </script>
</body>
</html>
"""

    return html

if __name__ == '__main__':
    tar_dir = '/Users/fabianosilva/Documentos/code/ddpai_extractor/working_data/tar'
    output_file = '/Users/fabianosilva/Documentos/code/ddpai_extractor/dashboard_merged.html'
    dashcam_root = '/Users/fabianosilva/dashcam/DCIM'

    # Merge trips 33-41
    trip_indices = list(range(33, 42))  # 33 to 41 inclusive

    merged_trip = merge_trips(tar_dir, trip_indices, output_file, dashcam_root)

    if merged_trip:
        build_dashboard_with_merged(tar_dir, merged_trip, output_file, dashcam_root)
