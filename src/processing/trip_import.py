#!/usr/bin/env python3
"""Discover dashcam trips and run the existing database builder."""
import argparse
from datetime import date, datetime, timedelta, timezone
import glob
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from src.extraction import build_database as builder

ROOT = Path(__file__).resolve().parents[2]


class IndexUnreadable(Exception):
    """data/trips.json exists but cannot be parsed as a trip index."""


def _remember(unreadable, errors):
    for path, _ in errors:
        if unreadable is not None and path not in unreadable:
            unreadable.append(path)


def group_points(group, unreadable=None):
    """GPS points of every archive in a group; unreadable archives are added to `unreadable`."""
    points = []
    for path in group:
        errors = []
        points.extend(builder.extract_gps_from_tar(path, errors=errors))
        _remember(unreadable, errors)
    return points


def choose_groups(groups, day, zone=None, unreadable=None):
    """Keep complete trips overlapping the local day, using GPS UTC when available."""
    selected = []
    for group in groups:
        start, end = local_trip_bounds(group, zone, unreadable=unreadable)
        if start.date() <= day <= end.date():
            selected.append(group)
    return selected


def local_trip_bounds(group, zone=None, points=None, unreadable=None):
    if points is None:
        points = group_points(group, unreadable)
    timestamps = [point['timestamp'] for point in points if isinstance(point.get('timestamp'), datetime)]
    if timestamps:
        return tuple(stamp.replace(tzinfo=timezone.utc).astimezone(zone) for stamp in (min(timestamps), max(timestamps)))
    start, _ = builder.parse_tar_filename(group[0])
    end, duration = builder.parse_tar_filename(group[-1])
    return (start.replace(tzinfo=timezone.utc).astimezone(zone),
            (end + timedelta(seconds=duration)).replace(tzinfo=timezone.utc).astimezone(zone))


def discover_groups(files, day, zone=None):
    """Trip groups of the local day plus every archive that could not be read.

    Returns (groups, parking_files, unreadable). Unreadable archives are classified as
    parked by the builder, but are reported separately so they are never dropped silently.
    """
    unreadable = []
    groups, _, parking = builder.detect_trip_groups(files, unreadable=unreadable)
    groups = choose_groups(groups, day, zone, unreadable=unreadable)
    return groups, parking, unreadable


def warn_unreadable(paths, out=None):
    paths = list(dict.fromkeys(paths))
    if not paths:
        return
    out = out or sys.stderr
    print("AVISO: {} arquivo(s) GPS ilegível(is) ou truncado(s). Eles NÃO são arquivos 'parados': "
          "o que deu para ler foi aproveitado e o resto se perdeu, então pode haver viagem ou pontos faltando. "
          "Verifique o cartão/arquivos:".format(len(paths)), file=out)
    for path in paths:
        print('  - {}'.format(path), file=out)


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


def load_index(path):
    """Parsed index, None if the file does not exist; IndexUnreadable if it is not a valid index."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise IndexUnreadable('{}: {}'.format(path, exc))
    if not isinstance(data, dict) or not isinstance(data.get('trips'), list):
        raise IndexUnreadable('{}: formato inesperado (esperado objeto com lista "trips")'.format(path))
    return data


def merge_index(old, new):
    """Trips of `new` replace same-id trips of `old`; all others are kept, ordered by id (UTC start)."""
    if old is None:
        merged = dict(new)
    else:
        merged = dict(new)
        merged.update({key: value for key, value in old.items() if key not in ('trips', 'generated_at')})
    by_id = {t['id']: t for t in (old or {}).get('trips', [])}
    by_id.update({t['id']: t for t in new['trips']})
    merged['trips'] = [by_id[key] for key in sorted(by_id)]
    return merged


_MARKER = re.compile(r'^' + re.escape(builder.REPORT_TRIP_MARKER) + r'(\S+)\s*$')
_SECTION = re.compile(r'^(REAR|FRONT) CAMERA - Merging \d+ videos:')


def _split_report(text, trip_ids):
    """(header_lines, {trip_id: block_lines}) or None when sections cannot be tied to trips.

    Reports written by the current builder tag each trip with a `TRIP: <id>` line. Older reports
    (no tags) carry two sections per trip in index order, which is how refresh_video_sync reads them.
    """
    lines = text.splitlines()
    marks = [i for i, line in enumerate(lines) if _MARKER.match(line)]
    if marks:
        blocks = {}
        for n, start in enumerate(marks):
            end = marks[n + 1] if n + 1 < len(marks) else len(lines)
            blocks[_MARKER.match(lines[start]).group(1)] = lines[start:end]
        return lines[:marks[0]], blocks
    firsts = [i for i, line in enumerate(lines) if _SECTION.match(line)]
    kinds = [_SECTION.match(lines[i]).group(1) for i in firsts]
    if len(firsts) != 2 * len(trip_ids) or kinds != ['REAR', 'FRONT'] * len(trip_ids):
        return None
    starts = []
    for i in firsts:
        start = i - 1 if i >= 1 and set(lines[i - 1]) == {'='} else i
        starts.append(start - 1 if start >= 1 and lines[start - 1] == '' else start)
    starts.append(len(lines))
    blocks = {}
    for n, trip_id in enumerate(trip_ids):
        blocks[trip_id] = [builder.report_trip_marker(trip_id)] + lines[starts[2 * n]:starts[2 * n + 2]]
    return lines[:starts[0]], blocks


def merge_reports(old_text, old_ids, new_text, new_ids, merged_ids):
    """Merge two merge reports so sections follow the merged index order; None if impossible."""
    old = _split_report(old_text, old_ids)
    new = _split_report(new_text, new_ids)
    if old is None or new is None:
        return None
    blocks = dict(old[1])
    blocks.update(new[1])
    lines = list(new[0])
    for trip_id in merged_ids:
        lines.extend(blocks.get(trip_id, []))
    return '\n'.join(lines)


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(path.parent), delete=False) as temp:
        try:
            temp.write(text)
            temp.flush()
            os.fsync(temp.fileno())
        except Exception:
            os.unlink(temp.name)
            raise
    os.replace(temp.name, str(path))


def _backup(path, backup_dir, prefix, stamp):
    backup = Path(backup_dir) / '{}-{}{}'.format(prefix, stamp, Path(path).suffix)
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(path), str(backup))
    return backup


def import_trips(paths, rear, front, root=ROOT, runner=subprocess.call, replace_unreadable_index=False, notify=print):
    """Build the given GPS archives and MERGE the result into root/data (never replace it)."""
    root = Path(root)
    index_path = root / 'data/trips.json'
    report_path = root / 'data/merge_report.txt'
    try:
        old = load_index(index_path)
    except IndexUnreadable as exc:
        if not replace_unreadable_index:
            notify('ERRO: índice existente ilegível, nada foi alterado: {}\n'
                   'Corrija/restaure o arquivo ou repita com --substituir-indice-ilegivel '
                   '(uma cópia dele será guardada em working_data/backups).'.format(exc))
            return 2
        notify('AVISO: índice ilegível será substituído (cópia guardada): {}'.format(exc))
        old = None
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup_dir = root / 'working_data/backups'
    if index_path.exists():
        notify('Índice anterior salvo em {}'.format(_backup(index_path, backup_dir, 'trips', stamp)))
    if report_path.exists():
        _backup(report_path, backup_dir, 'merge_report', stamp)
    with tempfile.TemporaryDirectory(prefix='ddpai-import-') as tmp:
        tar_dir = os.path.join(tmp, 'tar')
        out_dir = os.path.join(tmp, 'out')
        os.makedirs(tar_dir)
        os.makedirs(os.path.join(out_dir, 'data'))
        # The builder rewrites data/ from scratch; keep that in a scratch dir and merge afterwards,
        # while the merged videos still land in the real merged_videos/ through a link.
        (root / 'merged_videos').mkdir(exist_ok=True)
        os.symlink(str(root / 'merged_videos'), os.path.join(out_dir, 'merged_videos'))
        for path in paths:
            os.symlink(os.path.abspath(path), os.path.join(tar_dir, os.path.basename(path)))
        notify('Gerando GPS e vídeos para {} arquivo(s)...'.format(len(paths)))
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        rc = runner([str(root / 'build.sh'), tar_dir, str(rear), str(front), out_dir], cwd=str(root), env=env)
        if rc:
            return rc
        try:
            new = load_index(os.path.join(out_dir, 'data/trips.json'))
        except IndexUnreadable as exc:
            new = None
            notify('ERRO: a geração não produziu um índice válido: {}'.format(exc))
        if new is None:
            return 1
        merged = merge_index(old, new)
        new_report_path = os.path.join(out_dir, 'data/merge_report.txt')
        new_report = Path(new_report_path).read_text(encoding='utf-8') if os.path.exists(new_report_path) else ''
        report_text = new_report
        if old is not None and old['trips']:
            if not report_path.exists():
                merged_report = None
            else:
                merged_report = merge_reports(report_path.read_text(encoding='utf-8'), [t['id'] for t in old['trips']],
                                              new_report, [t['id'] for t in new['trips']], [t['id'] for t in merged['trips']])
            if merged_report is None:
                notify('AVISO: relatório de junção anterior ausente ou sem como associar suas seções às viagens; '
                       'o novo relatório cobre só esta importação (o anterior está em working_data/backups). '
                       'tools/refresh_video_sync.py recusará o índice até o relatório ser restaurado.')
            else:
                report_text = merged_report
        _atomic_write(report_path, report_text)
        _atomic_write(index_path, json.dumps(merged))
        notify('Índice mesclado: {} viagem(ns) no total ({} desta importação).'.format(len(merged['trips']), len(new['trips'])))
    return 0


def main():
    parser = argparse.ArgumentParser(description='Seleciona e processa viagens de um disco DDPAI.')
    parser.add_argument('--disco', help='Caminho do disco, se a detecção automática não funcionar')
    parser.add_argument('--data', help='Data local no formato AAAA-MM-DD (padrão: ontem)')
    parser.add_argument('--todas', action='store_true', help='Processa todas as viagens encontradas sem perguntar')
    parser.add_argument('--substituir-indice-ilegivel', action='store_true',
                        help='Se data/trips.json existir mas estiver corrompido, guarda uma cópia e começa um índice novo')
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
    try:
        load_index(ROOT / 'data/trips.json')
    except IndexUnreadable as exc:
        if not args.substituir_indice_ilegivel:
            print('ERRO: índice existente ilegível, nada foi alterado: {}\n'
                  'Corrija/restaure o arquivo ou use --substituir-indice-ilegivel.'.format(exc), file=sys.stderr)
            return 2
    files = sorted(str(path) for path in gps.glob('*.git'))
    print('Disco: {}\nAnalisando {} arquivos GPS para {}...'.format(disk, len(files), day), flush=True)
    groups, parking, unreadable = discover_groups(files, day)
    warn_unreadable(unreadable)
    if not groups:
        print('Nenhuma viagem detectada para essa data; {} arquivos foram classificados como parados ou sem GPS{}.'.format(
            len(parking), ' (incluindo {} ilegível(is), veja o aviso acima)'.format(len(set(unreadable))) if unreadable else ''))
        return 1
    print('\nViagens detectadas (horário local):')
    for index, group in enumerate(groups, 1):
        points = group_points(group)
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
    paths = [path for index in selected for path in groups[index]]
    return import_trips(paths, rear, front, replace_unreadable_index=args.substituir_indice_ilegivel)


if __name__ == '__main__':
    sys.exit(main())
