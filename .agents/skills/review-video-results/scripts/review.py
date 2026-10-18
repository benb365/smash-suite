"""Serve a fixed video-result viewer; no HTML generation or video conversion."""
import argparse
import copy
import json
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

TEMPLATE = Path(__file__).resolve().parents[1] / 'assets' / 'index.html'
COLORS = {'truth': '#35a778', 'excluded': '#e3a355'}
PREDICTION_COLORS = ['#5775e8', '#939eaf', '#a875cc', '#279eaa']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), f'{name} must be finite milliseconds')
    return value


def merged(parts):
    result = []
    for a, z in sorted((a, z) for a, z in parts if a < z):
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], z)
        else:
            result.append([a, z])
    return result


def duration(parts):
    return sum(z-a for a, z in merged(parts))


def intersection(a, b):
    return [(max(x, u), min(y, v)) for x, y in a for u, v in b if max(x, u) < min(y, v)]


def spans(rows):
    return [(r['start_ms'], r['end_ms']) for r in rows]


def check_summary(items, name):
    require(isinstance(items, list), f'{name} must be a list')
    for item in items:
        require(isinstance(item, dict) and all(isinstance(item.get(k), str) for k in ('label', 'value')), f'{name} cards need string label and value')


def prepare(data, base):
    """Validate the input and derive display intersections, preserving intervals."""
    data = copy.deepcopy(data)
    require(type(data.get('schema_version')) is int and data['schema_version'] == 1, 'schema_version must be 1')
    require(isinstance(data.get('title'), str) and data['title'].strip(), 'title is required')
    tracks = data.get('tracks')
    require(isinstance(tracks, list) and tracks, 'tracks must be a nonempty list')
    check_summary(data.get('summary', []), 'summary')
    ids = set()
    prediction_index = 0
    for t in tracks:
        require(isinstance(t, dict), 'each track must be an object')
        require(isinstance(t.get('id'), str) and t['id'] and t['id'] not in ids, 'track ids must be unique strings')
        require(isinstance(t.get('label'), str) and t['label'], f"track {t['id']}: label is required")
        require(t.get('role') in ('truth', 'prediction', 'excluded'), f"track {t['id']}: invalid role")
        ids.add(t['id'])
        if t['role'] == 'prediction':
            t['color'] = PREDICTION_COLORS[prediction_index % len(PREDICTION_COLORS)]
            prediction_index += 1
        else:
            t['color'] = COLORS[t['role']]
    truth_tracks = [t for t in tracks if t['role'] == 'truth']
    excluded_tracks = [t for t in tracks if t['role'] == 'excluded']
    predictions = [t for t in tracks if t['role'] == 'prediction']
    require(len(truth_tracks) <= 1 and len(excluded_tracks) <= 1, 'at most one truth and one excluded track')
    data['primary_track'] = data.get('primary_track', predictions[0]['id'] if predictions else None)
    require(data['primary_track'] in [t['id'] for t in predictions] or (not predictions and data['primary_track'] is None), 'primary_track must name a prediction track')
    clips = data.get('clips')
    require(isinstance(clips, list) and clips, 'clips must be a nonempty list')
    clip_ids = set()
    videos = []
    for index, c in enumerate(clips):
        require(isinstance(c, dict), 'each clip must be an object')
        cid = c.get('id')
        require(isinstance(cid, str) and cid and cid not in clip_ids, 'clip ids must be unique strings')
        clip_ids.add(cid)
        check_summary(c.get('summary', []), f'{cid}.summary')
        length = number(c.get('duration_ms'), f'{cid}.duration_ms')
        offset = number(c.get('media_offset_ms'), f'{cid}.media_offset_ms')
        require(length > 0 and offset >= 0, f'{cid}: duration must be positive, offset nonnegative')
        require(isinstance(c.get('video'), str) and c['video'], f'{cid}: video path is required')
        path = (base / c['video']).resolve()
        require(path.is_file(), f'{cid}: video does not exist: {path}')
        videos.append(path)
        c['video'] = f'/video/{index}'
        intervals = c.get('intervals')
        require(isinstance(intervals, dict) and set(intervals) == ids, f'{cid}: intervals must contain exactly the declared track ids')
        for t in tracks:
            rows = intervals[t['id']]
            require(isinstance(rows, list), f"{cid}.{t['id']}: expected an interval list")
            row_ids = set()
            for row in rows:
                require(isinstance(row, dict), f'{cid}: each interval must be an object')
                require(isinstance(row.get('id'), str) and row['id'] and row['id'] not in row_ids, f"{cid}.{t['id']}: interval ids must be unique strings")
                row_ids.add(row['id'])
                a = number(row.get('start_ms'), f'{cid}.start_ms')
                z = number(row.get('end_ms'), f'{cid}.end_ms')
                require(0 <= a < z <= length, f'{cid}: interval outside [0, duration_ms]')
                expected = {'truth': 'verified', 'excluded': 'human_confirmed'}.get(t['role'])
                require(expected is None or row.get('review_status') == expected, f"{cid}.{t['id']}: requires review_status={expected}")
            rows.sort(key=lambda r: (r['start_ms'], r['end_ms']))
        require(isinstance(c.get('issues', []), list), f'{cid}: issues must be a list')
        for issue in c.get('issues', []):
            require(isinstance(issue, dict), f'{cid}: each issue must be an object')
            require(isinstance(issue.get('label'), str) and issue['label'], f'{cid}: issue label is required')
            a = number(issue.get('start_ms'), f'{cid}.issue.start_ms')
            z = number(issue.get('end_ms'), f'{cid}.issue.end_ms')
            require(0 <= a < z <= length, f'{cid}: issue outside [0, duration_ms]')
        truth = intervals[truth_tracks[0]['id']] if truth_tracks else []
        excluded = intervals[excluded_tracks[0]['id']] if excluded_tracks else []
        all_truth = spans(truth)
        covered = merged(all_truth + spans(excluded))
        c['rows'] = []
        for actual in truth:
            target = [(actual['start_ms'], actual['end_ms'])]
            methods = {}
            for t in predictions:
                related = [p for p in intervals[t['id']] if intersection(spans([p]), target)]
                pp = spans(related)
                methods[t['id']] = dict(
                    intervals=related,
                    missing_ms=actual['end_ms']-actual['start_ms']-duration(intersection(pp, target)),
                    extra_ms=duration(pp)-duration(intersection(pp, covered)),
                    shared=any(sum(bool(intersection(spans([p]), spans([a]))) for a in truth) > 1 for p in related),
                )
            c['rows'].append(dict(truth=actual, methods=methods))
        c['other_outputs'] = []
        for t in predictions:
            for p in intervals[t['id']]:
                if not truth_tracks or not intersection(spans([p]), all_truth):
                    ignored = bool(truth_tracks and any(e['start_ms'] <= p['start_ms'] and p['end_ms'] <= e['end_ms'] for e in excluded))
                    c['other_outputs'].append(dict(track_id=t['id'], interval=p, ignored=ignored))
    return data, videos


def byte_range(header, size):
    if header is None:
        return 0, size-1, 200
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
    if not match or not any(match.groups()):
        raise ValueError('invalid range')
    start, end = match.groups()
    if not start:
        suffix = int(end)
        if suffix <= 0:
            raise ValueError('invalid suffix')
        a, z = max(0, size-suffix), size-1
    else:
        a, z = int(start), min(int(end), size-1) if end else size-1
    if a >= size or z < a:
        raise ValueError('unsatisfiable range')
    return a, z, 206


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        route = urlsplit(self.path).path
        if route in ('/', '/index.html', '/data.json'):
            content = TEMPLATE.read_bytes() if route != '/data.json' else self.server.payload
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8' if route == '/data.json' else 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if not head:
                self.wfile.write(content)
            return
        match = re.fullmatch(r'/video/(\d+)', route)
        if not match or int(match[1]) >= len(self.server.videos):
            self.send_error(404)
            return
        path = self.server.videos[int(match[1])]
        size = path.stat().st_size
        try:
            a, z, status = byte_range(self.headers.get('Range'), size)
        except ValueError:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(status)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(z-a+1))
        self.send_header('Accept-Ranges', 'bytes')
        if status == 206:
            self.send_header('Content-Range', f'bytes {a}-{z}/{size}')
        self.end_headers()
        if not head:
            try:
                with path.open('rb') as file:
                    file.seek(a)
                    remaining = z-a+1
                    while remaining:
                        block = file.read(min(65536, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18770)
    args = parser.parse_args()
    try:
        data, videos = prepare(json.loads(args.data.read_text()), args.data.resolve().parent)
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f'Cannot open review: {error}\n')
    server.payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
    server.videos = videos
    print(f'http://127.0.0.1:{server.server_port}/', flush=True)
    print(f'{len(videos)} videos; fixed template, saved intervals; Ctrl-C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
