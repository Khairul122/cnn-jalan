import os
import random
import tempfile
import unittest

from PIL import Image

from app.services.dedup_service import find_duplicate_groups


class TestDedupService(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = self.tmp.name
        os.makedirs(os.path.join(self.base_dir, 'app', 'static', 'uploads', 'foto'))

    def tearDown(self):
        self.tmp.cleanup()

    def _make_image(self, name, seed, size=(64, 64), noise=0):
        rel = f'uploads/foto/{name}'
        path = os.path.join(self.base_dir, 'app', 'static', rel)
        rng = random.Random(seed)
        pixels = []
        for _ in range(size[0] * size[1]):
            base = rng.randint(0, 255)
            pixels.append((base, base, base))
        if noise:
            pixels = [tuple(max(0, min(255, c + random.Random().randint(-noise, noise))) for c in p) for p in pixels]
        img = Image.new('RGB', size)
        img.putdata(pixels)
        img.save(path)
        return rel

    def test_near_identical_images_grouped_together(self):
        rel_a = self._make_image('a.jpg', seed=1)
        rel_b = self._make_image('b.jpg', seed=1, noise=3)   # nyaris identik dengan a (kompresi/resize beda tipis)
        rel_c = self._make_image('c.jpg', seed=2)            # foto lain, jelas beda

        groups = find_duplicate_groups([1, 2, 3], [rel_a, rel_b, rel_c], self.base_dir)

        self.assertEqual(groups[1], groups[2])
        self.assertNotEqual(groups[1], groups[3])

    def test_no_duplicates_gives_singleton_groups(self):
        rel_a = self._make_image('a.jpg', seed=1)
        rel_b = self._make_image('b.jpg', seed=2)

        groups = find_duplicate_groups([1, 2], [rel_a, rel_b], self.base_dir)

        self.assertEqual(len(set(groups.values())), 2)

    def test_missing_file_does_not_crash(self):
        rel_a = self._make_image('a.jpg', seed=1)
        groups = find_duplicate_groups([1, 2], [rel_a, 'uploads/foto/missing.jpg'], self.base_dir)
        self.assertIn(1, groups)
        self.assertIn(2, groups)


if __name__ == '__main__':
    unittest.main()
