#!/usr/bin/env python3
"""Discover dashcam trips and run the existing database builder."""
import argparse
from datetime import date, datetime, timedelta, timezone
import glob
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from src.extraction import build_database as builder

ROOT = Path(__file__).resolve().parents[2]


def choose_groups(groups, day, zone=None):
    """Keep complete trips overlapping the local day, using GPS UTC when available."""
    selected = []
    for group in groups:
        start, end = local_trip_bounds(group, zone)
        if start.date() <= day <= end.date():
            selected.append(group)
    return selected


def local_trip_bounds(group, zone=None, points=None):
    if points is None:
        points = [point for path in group for point in builder.extract_gps_from_tar(path)]
    timestamps = [point['timestamp'] for point in points if isinstance(point.get('timestamp'), datetime)]
    if timestamps:
        return tuple(stamp.replace(tzinfo=timezone.utc).astimezone(zone) for stamp in (min(timestamps), max(timestamps)))
    start, _ = builder.parse_tar_filename(group[0])
    end, duration = builder.parse_tar_filename(group[-1])
    return (start.replace(tzinfo=timezone.utc).astimezone(zone),
            (end + timedelta(seconds=duration)).replace(tzinfo=timezone.utc).astimezone(zone))


def parse_selection(value, count):
    if value.strip().lower() in ('t', 'todas', 'todos'):
        return list(range(count))
    try:
        indices = sorted(set(int(part.strip()) - 1 for part in value.split(',')))
    except ValueError:
        raise ValueError('Digite números separados por vírgulas ou T.')
    if not indices or any(index < 0 or index >= count for index in indices):
        raise ValueError('Seleção fora da lista.')
    return indices


def find_disks():
    roots = glob.glob('/run/media/*/*') + glob.glob('/media/*/*') + glob.glob('/Volumes/*')
    return sorted(set(Path(root) for root in roots if (Path(root) / 'DCIM/203gps/tar').is_dir()))


def main():
    parser = argparse.ArgumentParser(description='Seleciona e processa viagens de um disco DDPAI.')
    parser.add_argument('--disco', help='Caminho do disco, se a detecção automática não funcionar')
    parser.add_argument('--data', help='Data local no formato AAAA-MM-DD (padrão: ontem)')
    parser.add_argument('--todas', action='store_true', help='Processa todas as viagens encontradas sem perguntar')
    args = parser.parse_args()
    try:
        day = datetime.strptime(args.data, '%Y-%m-%d').date() if args.data else date.today() - timedelta(days=1)
    except ValueError:
        parser.error('Data inválida; use AAAA-MM-DD.')
    disks = [Path(args.disco)] if args.disco else find_disks()
    if not disks:
        parser.error('Nenhum disco DDPAI encontrado. Conecte-o ou use --disco CAMINHO.')
    if len(disks) > 1:
        print('Discos encontrados:')
        for i, disk in enumerate(disks, 1):
            print('  {}. {}'.format(i, disk))
        try:
            disk_number = int(input('Escolha o disco: '))
            if disk_number < 1 or disk_number > len(disks):
                raise ValueError('Disco inválido')
            disk = disks[disk_number - 1]
        except (ValueError, IndexError):
            parser.error('Disco inválido.')
    else:
        disk = disks[0]
    gps = disk / 'DCIM/203gps/tar'
    rear = disk / 'DCIM/200video/rear'
    front = disk / 'DCIM/200video/front'
    if not all(path.is_dir() for path in (gps, rear, front)):
        parser.error('Disco incompleto: são necessárias as pastas de GPS, vídeo traseiro e dianteiro.')
    files = sorted(str(path) for path in gps.glob('*.git'))
    print('Disco: {}\nAnalisando {} arquivos GPS para {}...'.format(disk, len(files), day), flush=True)
    groups, _, parking = builder.detect_trip_groups(files)
    groups = choose_groups(groups, day)
    if not groups:
        print('Nenhuma viagem detectada para essa data; {} arquivos foram classificados como parados ou sem GPS.'.format(len(parking)))
        return 1
    print('\nViagens detectadas (horário local):')
    for index, group in enumerate(groups, 1):
        points = []
        for path in group:
            points.extend(builder.extract_gps_from_tar(path))
        start, end = local_trip_bounds(group, points=points)
        stats = builder.compute_trip_stats(points)
        print('  {}. {} → {} | {:.1f} km | {} arquivo(s)'.format(index, start.strftime('%d/%m %H:%M'), end.strftime('%d/%m %H:%M'), stats['distance_km'], len(group)))
    print('Observação: arquivos classificados como parados ou sem GPS são excluídos.')
    if args.todas:
        selected = list(range(len(groups)))
    else:
        while True:
            choice = input('Escolha números separados por vírgula, T para todas ou Q para sair: ').strip()
            if choice.lower() == 'q':
                return 0
            try:
                selected = parse_selection(choice, len(groups))
                break
            except ValueError as exc:
                print(exc)
    previous = ROOT / 'data/trips.json'
    if previous.exists():
        backup_dir = ROOT / 'working_data' / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / ('trips-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        shutil.copy2(str(previous), str(backup))
        print('Índice anterior salvo em {}'.format(backup), flush=True)
    with tempfile.TemporaryDirectory(prefix='ddpai-import-') as tmp:
        for index in selected:
            for path in groups[index]:
                os.symlink(os.path.abspath(path), os.path.join(tmp, os.path.basename(path)))
        print('Gerando GPS e vídeos para {} viagem(ns)...'.format(len(selected)), flush=True)
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        return subprocess.call([str(ROOT / 'build.sh'), tmp, str(rear), str(front), str(ROOT)], cwd=str(ROOT), env=env)


if __name__ == '__main__':
    sys.exit(main())
