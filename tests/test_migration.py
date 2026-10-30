import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from app.migration import copy_data, validate_destination
from app import paths
from app.config import Config
from app.storage import Store

class MigrationTests(unittest.TestCase):
    def test_redirected_profile_locator_write_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            control = Path(t)/'control'
            target = Path(t)/'data'
            error = OSError('invalid handle')
            error.winerror = 6
            with patch.object(paths,'CONTROL',control),patch.object(paths,'LOCATOR',control/'location.json'),patch.object(paths,'_data',control):
                with patch.object(Path,'replace',side_effect=error):
                    paths.select_directory(target)
                # Windows temp directories may use an 8.3 alias (RUNNER~1).
                # The app deliberately persists the resolved absolute path.
                self.assertEqual(paths.data_dir(),target.resolve())
                self.assertEqual(json.loads(paths.LOCATOR.read_text(encoding='utf-8'))['data_dir'],str(target.resolve()))

    def test_copy_preserves_source_and_rewrites_snapshot_links(self):
        with tempfile.TemporaryDirectory() as t:
            src,dst=Path(t)/'old',Path(t)/'new'
            (src/'snapshots').mkdir(parents=True)
            (src/'snapshots/a.jpg').write_bytes(b'test-only-image')
            (src/'settings.json').write_text('{"repeat": 45}',encoding='utf-8')
            with closing(sqlite3.connect(src/'events.sqlite3')) as c, c:
                c.execute('CREATE TABLE events (id TEXT, image TEXT)')
                c.execute('INSERT INTO events VALUES (?,?)',('a',str(src/'snapshots/a.jpg')))
            before=(src/'events.sqlite3').read_bytes()
            result=copy_data(src,dst)
            self.assertEqual(result['files'],3)
            self.assertEqual((dst/'settings.json').read_bytes(),(src/'settings.json').read_bytes())
            self.assertEqual((src/'events.sqlite3').read_bytes(),before)
            with closing(sqlite3.connect(dst/'events.sqlite3')) as c:
                self.assertEqual(c.execute('SELECT image FROM events').fetchone()[0],str((dst/'snapshots/a.jpg').resolve()))
            self.assertEqual((dst/'snapshots/a.jpg').read_bytes(),b'test-only-image')

    def test_nonempty_target_never_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            src,dst=Path(t)/'a',Path(t)/'b'
            src.mkdir();dst.mkdir()
            (dst/'keep.txt').write_text('keep')
            with self.assertRaises(ValueError):
                copy_data(src,dst)
            self.assertEqual((dst/'keep.txt').read_text(),'keep')

    def test_nested_paths_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                validate_destination(t,Path(t)/'child')

    def test_config_and_new_events_follow_new_directory(self):
        with tempfile.TemporaryDirectory() as t:
            control,src,dst=Path(t)/'control',Path(t)/'a',Path(t)/'b'
            control.mkdir()
            with patch.object(paths,'CONTROL',control),patch.object(paths,'LOCATOR',control/'location.json'),patch.object(paths,'_data',src):
                c=Config(repeat=47)
                c.save()
                store=Store()
                store.submit('before',{})
                self.assertTrue(store.close())
                copy_data(src,dst)
                paths.select_directory(dst)
                self.assertEqual(json.loads(paths.LOCATOR.read_text(encoding='utf-8'))['data_dir'],str(dst.resolve()))
                self.assertEqual(Config.load().repeat,47)
                c.repeat=51;c.save()
                self.assertEqual(json.loads((src/'settings.json').read_text(encoding='utf-8'))['repeat'],47)
                self.assertEqual(json.loads((dst/'settings.json').read_text(encoding='utf-8'))['repeat'],51)
                store=Store();store.submit('after',{});self.assertTrue(store.close())
                with closing(sqlite3.connect(src/'events.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
                with closing(sqlite3.connect(dst/'events.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],2)

if __name__=='__main__':
    unittest.main()
