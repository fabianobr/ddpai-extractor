#!/usr/bin/env python3
"""Refresh GPS/video mappings in an existing database without re-merging media."""
import argparse
import glob
import json
import os
import re
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.extraction import build_database as builder
from src.extraction.video_timeline import build_video_sync


DEFAULT_INDEX_MODE = 0o644


def write_index_atomic(data, database):
    """Write JSON via temp file + os.replace, keeping the original file permissions."""
    database = Path(database)
    try:
        mode = stat.S_IMODE(os.stat(str(database)).st_mode)
    except OSError:
        mode = DEFAULT_INDEX_MODE
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=str(database.parent), delete=False) as temp:
        try:
            json.dump(data, temp)
            temp.flush()
            os.fsync(temp.fileno())
            os.chmod(temp.name, mode)
        except Exception:
            os.unlink(temp.name)
            raise
    os.replace(temp.name, str(database))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disco', required=True, help='Root of the DDPAI disk')
    parser.add_argument('--database', default=str(ROOT / 'data/trips.json'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    disk = Path(args.disco)
    gps = disk / 'DCIM/203gps/tar'
    rear = disk / 'DCIM/200video/rear'
    front = disk / 'DCIM/200video/front'
    if not all(p.is_dir() for p in (gps, rear, front)):
        parser.error('GPS, rear or front directory missing')
    database = Path(args.database)
    data = json.loads(database.read_text(encoding='utf-8'))
    builder.VIDEO_DIR_REAR = str(rear)
    builder.VIDEO_DIR_FRONT = str(front)
    # Membership must match the trips that were already imported and merged. Archives that
    # looked like driving only because of stale buffer residue would now be classed as
    # parked and leave the group (changing the video range); drop_stale=False keeps them.
    # Points themselves are still extracted with the residue removed.
    groups, _, _ = builder.detect_trip_groups(sorted(glob.glob(str(gps / '*.git'))), drop_stale=False)
    by_id = {}
    for group in groups:
        start, _ = builder.parse_tar_filename(group[0])
        by_id[start.strftime('%Y%m%d%H%M%S')] = group
    expected_ids = [trip['id'] for trip in data['trips']]
    missing = [identifier for identifier in expected_ids if identifier not in by_id]
    if missing:
        raise SystemExit('Arquivos GPS ausentes para: ' + ', '.join(missing))
    # A saved merge report records the exact order used to build each output.
    # Do not infer that identical file counts mean identical inputs.
    report = database.parent / 'merge_report.txt'
    if not report.exists():
        raise SystemExit('Relatório original de junção ausente; não é possível confirmar a ordem dos vídeos.')
    sections = re.findall(r'(REAR|FRONT) CAMERA - Merging (\d+) videos:(.*?)Total Videos:',
                          report.read_text(encoding='utf8'), re.S)
    if len(sections) != 2 * len(data['trips']):
        raise SystemExit('Relatório de junção não corresponde às viagens do índice.')
    for trip_index, trip in enumerate(data['trips']):
        group = by_id[trip['id']]
        points = []
        for path in group:
            points.extend(builder.extract_gps_from_tar(path))
        points.sort(key=lambda point: point['timestamp'])
        if not points:
            raise SystemExit('GPS vazio: ' + trip['id'])
        rear_videos = builder.discover_videos(group, camera='rear')
        front_videos = builder.discover_videos(group, camera='front')
        if rear_videos and front_videos:
            count = min(len(rear_videos), len(front_videos))
            rear_videos, front_videos = rear_videos[:count], front_videos[:count]
        rear_videos = rear_videos if trip.get('video_rear') else []
        front_videos = front_videos if trip.get('video_front') else []
        # Preserve exact original source selection: refuse if the source counts changed.
        expected = trip.get('video_notes', '')
        match = re.search(r'Merged (\d+) rear \+ (\d+) front videos', expected)
        if match and (len(rear_videos) != int(match.group(1)) or len(front_videos) != int(match.group(2))):
            raise SystemExit('Segmentos atuais divergem dos usados na junção: ' + trip['id'])
        for camera, paths, section in zip(('REAR', 'FRONT'), (rear_videos, front_videos), sections[trip_index * 2:trip_index * 2 + 2]):
            source_names = re.findall(r'^\s*\d+\. ([^\n]+\.mp4)$', section[2], re.M)
            if section[0] != camera or source_names != [Path(path).name for path in paths]:
                raise SystemExit('Ordem dos segmentos {} diverge do relatório: {}'.format(camera, trip['id']))
        print('Analisando {} ({} pontos, {}+{} vídeos)...'.format(trip['id'], len(points), len(rear_videos), len(front_videos)), flush=True)
        sync = build_video_sync(points, rear_videos, front_videos, builder.extract_video_duration)
        for camera in ('rear', 'front'):
            media_path = trip.get('video_' + camera)
            if not media_path:
                continue
            merged_duration = builder.extract_video_duration(str(ROOT / media_path))
            source_duration = sync[camera + '_source_duration_s']
            if merged_duration is None or abs(merged_duration - source_duration) > 5:
                raise SystemExit('Duração do vídeo {} diverge dos segmentos para {}: {} vs {}'.format(camera, trip['id'], merged_duration, source_duration))
        before_points = len(trip.get('points', []))
        before_sync = trip.get('video_sync') or {}
        print('  pontos: {} -> {} ({:+d}) | pontos sem vídeo (null) rear/front: {}/{} -> {}/{}'.format(
            before_points, len(points), len(points) - before_points,
            sum(x is None for x in before_sync.get('rear', [])), sum(x is None for x in before_sync.get('front', [])),
            sum(x is None for x in sync['rear']), sum(x is None for x in sync['front'])), flush=True)
        print('  {} | relógio GPS − câmera: {} s (dispersão máx {} s, típica {} s, {} discrepantes de {} segmentos, confiança {}) | pontos com vídeo rear/front: {}/{} de {}'.format(
            sync['status'], sync['clock_offset_s'], sync['offset_spread_s'], sync['offset_typical_spread_s'], sync['offset_outlier_segments'], sync['offset_samples'], sync['confidence'],
            sum(x is not None for x in sync['rear']),
            sum(x is not None for x in sync['front']), len(points)), flush=True)
        first = points[0]['timestamp']
        last = points[-1]['timestamp']
        first_local = first.replace(tzinfo=timezone.utc).astimezone()
        last_local = last.replace(tzinfo=timezone.utc).astimezone()
        trip['label'] = '{} → {}'.format(first_local.strftime('%d/%m %H:%M'), last_local.strftime('%d/%m %H:%M'))
        trip['date'] = first_local.date().isoformat()
        trip['duration_min'] = round((last - first).total_seconds() / 60, 1)
        stats = builder.compute_trip_stats(points)
        for key in ('distance_km', 'max_speed', 'avg_speed'):
            trip[key] = stats[key]
        trip['points'] = [[p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading'],
                           round((p['timestamp'] - first).total_seconds(), 2)] for p in points]
        trip['video_sync'] = sync
        trip['start_timestamp'] = first.isoformat()
        trip['gps_points_count'] = len(points)
        trip['sparse_timestamps'] = builder.compute_sparse_timestamps(points, sample_interval=10)
        trip['idle_segments'] = [{k: value for k, value in segment.items() if k != 'points'}
                                 for segment in builder.detect_idle_segments(points)]
        gps_duration = (points[-1]['timestamp'] - first).total_seconds()
        trip['video_duration_status'] = builder.validate_video_gps_duration(trip.get('video_duration_s'), gps_duration)
    if args.dry_run:
        print('Simulação: índice original preservado.')
        return
    backup_dir = ROOT / 'working_data/backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / ('trips-before-sync-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    shutil.copy2(str(database), str(backup))
    data['sync_refreshed_at'] = datetime.now(timezone.utc).isoformat()
    write_index_atomic(data, database)
    print('Atualizado: {} | backup: {}'.format(database, backup), flush=True)


if __name__ == '__main__':
    main()
