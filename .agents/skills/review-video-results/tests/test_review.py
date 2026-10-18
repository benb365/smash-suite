import copy
import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location('review', Path(__file__).resolve().parents[1]/'scripts/review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        (self.base/'clip.mp4').write_bytes(b'0123456789abcdef')
        self.data = dict(schema_version=1, title='Test', tracks=[
            dict(id='truth', label='人工', role='truth'),
            dict(id='current', label='算法', role='prediction'),
            dict(id='excluded', label='排除', role='excluded')], clips=[dict(
                id='clip', video='clip.mp4', duration_ms=10000, media_offset_ms=91,
                intervals=dict(truth=[dict(id='1',start_ms=1000,end_ms=3000,review_status='verified')],
                               current=[dict(id='1',start_ms=1500,end_ms=3500)], excluded=[]))])

    def test_display_intersection_and_input_unchanged(self):
        before = copy.deepcopy(self.data)
        data, paths = review.prepare(self.data, self.base)
        method = data['clips'][0]['rows'][0]['methods']['current']
        self.assertEqual((method['missing_ms'], method['extra_ms']), (500, 500))
        self.assertEqual(method['intervals'], self.data['clips'][0]['intervals']['current'])
        self.assertEqual(data['clips'][0]['media_offset_ms'], 91)
        self.assertEqual(paths, [(self.base/'clip.mp4').resolve()])
        self.assertEqual(self.data, before)

    def test_union_shared_output_and_exclusion(self):
        c = self.data['clips'][0]
        c['intervals']['truth'].append(dict(id='2',start_ms=4000,end_ms=5000,review_status='verified'))
        c['intervals']['current'] = [dict(id='1',start_ms=1000,end_ms=5500),dict(id='2',start_ms=2000,end_ms=4500)]
        c['intervals']['excluded'] = [dict(id='e',start_ms=5000,end_ms=5500,review_status='human_confirmed')]
        data, _ = review.prepare(self.data, self.base)
        rows = data['clips'][0]['rows']
        for row in rows:
            self.assertEqual(row['methods']['current']['missing_ms'], 0)
            self.assertEqual(row['methods']['current']['extra_ms'], 1000)
            self.assertTrue(row['methods']['current']['shared'])

    def test_no_truth_and_ignored_only_if_fully_contained(self):
        c = self.data['clips'][0]
        c['intervals']['current'] = [dict(id='1',start_ms=6000,end_ms=6500),dict(id='2',start_ms=6900,end_ms=7200)]
        c['intervals']['excluded'] = [dict(id='e',start_ms=6000,end_ms=7000,review_status='human_confirmed')]
        data, _ = review.prepare(self.data, self.base)
        self.assertEqual([p['ignored'] for p in data['clips'][0]['other_outputs']], [True, False])
        self.data['tracks'] = self.data['tracks'][1:]
        del c['intervals']['truth']
        data, _ = review.prepare(self.data, self.base)
        self.assertEqual(data['clips'][0]['rows'], [])
        self.assertFalse(any(p['ignored'] for p in data['clips'][0]['other_outputs']))

    def test_invalid_input_rejected(self):
        for value in (float('nan'), float('inf'), '2000', -1, 11000):
            with self.subTest(value=value):
                data = copy.deepcopy(self.data)
                data['clips'][0]['intervals']['current'][0]['end_ms'] = value
                with self.assertRaises(ValueError):
                    review.prepare(data, self.base)
        for status in ('needs_review', None):
            self.data['clips'][0]['intervals']['truth'][0]['review_status'] = status
            with self.assertRaisesRegex(ValueError, 'verified'):
                review.prepare(self.data, self.base)

    def test_http_ranges_and_only_declared_files(self):
        data, paths = review.prepare(self.data, self.base)
        server = ThreadingHTTPServer(('127.0.0.1', 0), review.Handler)
        server.payload = json.dumps(data).encode()
        server.videos = paths
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown(); server.server_close(); thread.join()
        self.addCleanup(stop)
        url = f'http://127.0.0.1:{server.server_port}'
        for header, content, content_range in [('bytes=2-5',b'2345','bytes 2-5/16'),('bytes=12-',b'cdef','bytes 12-15/16'),('bytes=-3',b'def','bytes 13-15/16')]:
            with urlopen(Request(url+'/video/0', headers={'Range':header})) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), content)
                self.assertEqual(response.headers['Content-Range'], content_range)
        with urlopen(Request(url+'/video/0', method='HEAD')) as response:
            self.assertEqual(response.headers['Content-Length'], '16')
            self.assertEqual(response.read(), b'')
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(url+'/video/0', headers={'Range':'bytes=99-'}))
        self.assertEqual(error.exception.code, 416)
        with self.assertRaises(HTTPError) as error:
            urlopen(url+'/../clip.mp4')
        self.assertEqual(error.exception.code, 404)
        with urlopen(url+'/data.json') as response:
            self.assertEqual(json.load(response)['clips'][0]['intervals'], data['clips'][0]['intervals'])


if __name__ == '__main__':
    unittest.main()
