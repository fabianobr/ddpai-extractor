#!/usr/bin/env python3
"""
Convert DDPAI GPS NMEA files to merged GPX, ignoring bad checksums.
"""
import sys
import os
import glob
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

def parse_nmea_sentence(sentence):
    """Parse NMEA sentence, ignoring checksum."""
    if not sentence.startswith('$'):
        return None

    # Remove checksum part
    if '*' in sentence:
        sentence = sentence[:sentence.index('*')]

    parts = sentence[1:].split(',')
    if len(parts) < 2:
        return None

    sentence_type = parts[0]
    return {'type': sentence_type, 'data': parts[1:]}

def parse_rmc(data):
    """Parse RMC sentence (Recommended Minimum Navigation Information)."""
    if len(data) < 11:
        return None

    try:
        time_str = data[0]
        status = data[1]  # A=active/valid, V=void/invalid
        lat_str = data[2]
        lat_dir = data[3]
        lon_str = data[4]
        lon_dir = data[5]

        if status != 'A' or not lat_str or not lon_str:
            return None

        # Convert DDMM.MMMMM format to decimal degrees
        lat = dms_to_decimal(lat_str, lat_dir)
        lon = dms_to_decimal(lon_str, lon_dir)

        if lat is None or lon is None:
            return None

        # Get optional speed and heading
        speed = data[6] if len(data) > 6 and data[6] else None
        heading = data[7] if len(data) > 7 and data[7] else None

        return {
            'time': time_str,
            'lat': lat,
            'lon': lon,
            'speed': speed,
            'heading': heading
        }
    except (ValueError, IndexError):
        return None

def dms_to_decimal(coord_str, direction):
    """Convert DDMM.MMMMM format to decimal degrees."""
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

def process_nmea_file(input_file):
    """Extract valid GPS points from NMEA file."""
    points = []

    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parsed = parse_nmea_sentence(line)
                if not parsed:
                    continue

                if parsed['type'] in ['GPRMC', 'GNRMC']:
                    point = parse_rmc(parsed['data'])
                    if point:
                        points.append(point)
    except Exception as e:
        print(f"Error reading {input_file}: {e}")

    return points

def create_gpx(all_points, output_file):
    """Create GPX file from GPS points."""
    ns = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace('', ns)

    gpx = ET.Element('gpx', {
        'version': '1.1',
        'creator': 'ddpai_route_improved.py',
        'xmlns': ns
    })

    # Add metadata
    metadata = ET.SubElement(gpx, 'metadata')
    time_elem = ET.SubElement(metadata, 'time')
    time_elem.text = datetime.utcnow().isoformat() + 'Z'

    # Create track
    trk = ET.SubElement(gpx, 'trk')
    name = ET.SubElement(trk, 'name')
    name.text = 'DDPAI Trip'

    # Add all points as track segment
    if all_points:
        trkseg = ET.SubElement(trk, 'trkseg')

        for point in all_points:
            trkpt = ET.SubElement(trkseg, 'trkpt', {
                'lat': str(point['lat']),
                'lon': str(point['lon'])
            })

            # Add elevation (optional)
            # ele = ET.SubElement(trkpt, 'ele')
            # ele.text = str(point.get('elevation', 0))

    tree = ET.ElementTree(gpx)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Generated: {output_file} ({len(all_points)} points)")

def main():
    input_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'converted_routes_improved'

    Path(out_dir).mkdir(exist_ok=True)

    print(f"Processing files in: {input_dir}")

    all_points = []
    file_count = 0

    for gpx_file in sorted(glob.glob(os.path.join(input_dir, '*.gpx'))):
        basename = os.path.basename(gpx_file)
        print(f"Processing: {basename}")

        points = process_nmea_file(gpx_file)
        if points:
            all_points.extend(points)
            file_count += 1
            print(f"  -> {len(points)} valid points")
        else:
            print(f"  -> no valid points")

    if not all_points:
        print("No valid GPS points found!")
        return 1

    print(f"\nTotal: {len(all_points)} points from {file_count} files")

    # Create merged GPX
    merged_file = os.path.join(out_dir, 'merged_trip.gpx')
    create_gpx(all_points, merged_file)

    print(f"Final file: {merged_file}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
