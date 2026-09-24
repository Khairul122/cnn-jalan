import os
import random
import tempfile
import unittest

from PIL import Image

from app.services.dedup_service import find_duplicate_groups, find_spatial_groups, merge_group_maps


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

    def test_spatial_groups_link_chains_and_ignore_far_points(self):
        # ~0.00045 derajat lintang ~= 50 m. A-B 50 m, B-C 50 m (rantai), D jauh.
        d = 0.00045
        coords = [(5.18, 97.14), (5.18 + d, 97.14), (5.18 + 2 * d, 97.14), (5.30, 97.14)]
        g = find_spatial_groups([1, 2, 3, 4], coords, radius_m=60)
        self.assertEqual(g[1], g[2])
        self.assertEqual(g[2], g[3])          # single linkage: A dekat B, B dekat C -> satu grup
        self.assertNotEqual(g[3], g[4])
        g0 = find_spatial_groups([1, 2, 3, 4], coords, radius_m=0)
        self.assertEqual(len(set(g0.values())), 4)   # radius 0 = semua singleton

    def test_merge_group_maps_unions_both_sources(self):
        dup = {1: 1, 2: 1, 3: 3, 4: 4}        # 1~2 near-duplicate
        spasial = {1: 1, 2: 2, 3: 3, 4: 3}    # 3~4 berdekatan
        m = merge_group_maps([1, 2, 3, 4], dup, spasial)
        self.assertEqual(m[1], m[2])
        self.assertEqual(m[3], m[4])
        self.assertNotEqual(m[1], m[3])


if __name__ == '__main__':
    unittest.main()
