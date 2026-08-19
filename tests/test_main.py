import tempfile
import unittest
from types import SimpleNamespace

from main import category_names, cmd_classify
from src.config import DEFAULT_CONFIG
from src.repository import Repository


class MainPipelineTests(unittest.TestCase):
    def make_config(self):
        return SimpleNamespace(
            categories=DEFAULT_CONFIG["categories"],
            min_confidence=DEFAULT_CONFIG["min_confidence"],
        )

    def test_category_names_follow_config_dimensions(self):
        names = category_names(self.make_config())
        self.assertIn("普通话", names)
        self.assertIn("摇滚", names)
        self.assertIn("抒情", names)

    def test_classify_reads_qq_metadata_cache_without_ai(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            repo.save_songs(
                [{"mid": "song-1", "name": "Example", "singer": "Singer", "album": "Album"}]
            )
            repo.save_metadata_item(
                "song-1",
                {"language": "英语", "genre": "摇滚", "tags": ["热血"]},
            )

            self.assertEqual(cmd_classify(self.make_config(), repo), 0)
            result = repo.load_songs()[0]["classification"]
            self.assertEqual(result["categories"]["language"], ["英语"])
            self.assertEqual(result["categories"]["genre"], ["摇滚"])
            self.assertEqual(result["categories"]["emotion"], ["热血"])


if __name__ == "__main__":
    unittest.main()
