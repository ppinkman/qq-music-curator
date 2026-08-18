import tempfile
import unittest

from src.repository import Repository


class RepositoryTests(unittest.TestCase):
    def test_save_songs_preserves_order_and_updates_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            repo.save_songs(
                [
                    {"mid": "a", "name": "old"},
                    {"mid": "b", "name": "second"},
                    {"mid": "a", "name": "new"},
                ]
            )
            songs = repo.load_songs()
            self.assertEqual([song["mid"] for song in songs], ["a", "b"])
            self.assertEqual(songs[0]["name"], "new")

    def test_metadata_update_replaces_same_mid(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            repo.save_metadata_item("a", {"language": "英语"})
            repo.save_metadata_item("a", {"language": "粤语"})
            self.assertEqual(repo.load_metadata_cache()["a"]["language"], "粤语")
            with open(repo.metadata_cache_file, "r", encoding="utf-8") as handle:
                self.assertEqual(len(handle.readlines()), 1)

    def test_old_checkpoint_begin_field_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            with open(repo.checkpoint_file, "w", encoding="utf-8") as handle:
                handle.write('{"begin": 200, "fetched_count": 200}')
            self.assertEqual(repo.load_checkpoint()["next_begin"], 200)


if __name__ == "__main__":
    unittest.main()
