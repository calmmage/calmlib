from tempfile import NamedTemporaryFile
from unittest import TestCase

from calmlib.read_write import dump, load


class TestReadWrite(TestCase):
    def test_dump_load(self):
        with NamedTemporaryFile('r+', suffix='.json') as f:
            obj = {'test_key': 'test_val'}
            dump(obj, f.name)
            f.seek(0)
            self.assertEqual(obj, load(f.name))

        with NamedTemporaryFile('r+b', suffix='.pickle') as f:
            obj = {'test_key': 'test_val'}
            dump(obj, f.name)
            f.seek(0)
            self.assertEqual(obj, load(f.name))
