import unittest

from src.codex_curator import CodexMusicCurator


class CodexCuratorTests(unittest.TestCase):
    def setUp(self):
        self.curator = CodexMusicCurator()

    def test_qq_labels_do_not_change_result(self):
        base = {"mid": "1", "name": "开到荼蘼", "singer": "王菲", "album": "只爱陌生人"}
        changed = {**base, "language": "英语", "genre": "金属", "tags": ["摇滚"]}
        self.assertEqual(
            self.curator.classify(base, "1999-09-10")["categories"],
            self.curator.classify(changed, "1999-09-10")["categories"],
        )

    def test_kpop_is_not_mislabeled_as_western_female(self):
        result = self.curator.classify(
            {"name": "Ditto", "singer": "NewJeans (뉴진스)", "album": "OMG"},
            "2023-01-02",
        )
        self.assertNotIn("欧美女声", result["categories"])
        self.assertIn("梦幻迷幻", result["categories"])

    def test_western_girl_duo_is_western_female(self):
        result = self.curator.classify(
            {"name": "Pretty Boy", "singer": "M2M", "album": "Shades of Purple"},
            "2000-03-07",
        )
        self.assertIn("欧美女声", result["categories"])
        self.assertIn("千禧欧美", result["categories"])
        self.assertIn("Y2K 氛围", result["categories"])

    def test_narrow_styles_are_track_level(self):
        plain = self.curator.classify(
            {"name": "南海姑娘", "singer": "王菲", "album": "邓丽君故乡情"},
            "1990-01-01",
        )
        dreamy = self.curator.classify(
            {"name": "开到荼蘼", "singer": "王菲", "album": "只爱陌生人"},
            "1999-09-10",
        )
        self.assertNotIn("梦幻迷幻", plain["categories"])
        self.assertIn("梦幻迷幻", dreamy["categories"])

    def test_live_variant_uses_earliest_comparable_year(self):
        songs = [
            {"mid": "a", "name": "暗涌", "singer": "王菲", "album": "玩具"},
            {"mid": "b", "name": "暗涌 (Live)", "singer": "王菲", "album": "现场"},
        ]
        metadata = {
            "a": {"release_date": "1997-02-20"},
            "b": {"release_date": "2015-01-01"},
        }
        results = self.curator.classify_all(songs, metadata)
        self.assertIn("90 年代华语", results["b"]["categories"])
        self.assertEqual(1997, results["b"]["input_evidence"]["effective_year"])


if __name__ == "__main__":
    unittest.main()
