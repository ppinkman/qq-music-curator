import tempfile
import unittest

from src.qqmusic_importer import QQMusicPlaylistImporter, build_playlist_targets
from src.repository import Repository


class FakeQQMusicAPI:
    def __init__(self):
        self.playlists = [
            {"name": "AI·甲", "dirid": "1", "tid": "101", "song_count": 1}
        ]
        self.songs = {"1": {"a"}}
        self.add_calls = []

    def list_created_playlists(self):
        return list(self.playlists)

    def create_playlist(self, name):
        dirid = str(len(self.playlists) + 1)
        self.playlists.append(
            {"name": name, "dirid": dirid, "tid": "", "song_count": 0}
        )
        self.songs[dirid] = set()
        return dirid

    def get_playlist_song_mids(self, dirid):
        return set(self.songs[str(dirid)])

    def add_songs_to_playlist(self, dirid, mids):
        song_mids = [song["mid"] for song in mids]
        self.add_calls.append((str(dirid), song_mids))
        self.songs[str(dirid)].update(song_mids)
        return len(mids)

    def edit_playlist_name(self, dirid, name):
        for playlist in self.playlists:
            if playlist["dirid"] == str(dirid):
                playlist["name"] = name
                return True
        return False


class QQMusicImporterTests(unittest.TestCase):
    def test_build_targets_keeps_multilabel_and_routes_unassigned_to_review(self):
        songs = [
            {
                "mid": "a",
                "classification": {
                    "categories": ["甲", "乙"],
                    "needs_review": False,
                },
            },
            {
                "mid": "b",
                "classification": {"categories": [], "needs_review": True},
            },
        ]
        targets = build_playlist_targets(songs, categories=["甲", "乙"])
        self.assertEqual(targets["AI·甲"], ["a"])
        self.assertEqual(targets["AI·乙"], ["a"])
        self.assertEqual(targets["AI·待复核"], ["b"])

    def test_import_is_idempotent_and_adds_only_missing_songs(self):
        api = FakeQQMusicAPI()
        targets = {"AI·甲": ["a", "b"], "AI·乙": ["c"]}
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            importer = QQMusicPlaylistImporter(
                api,
                repo,
                songs=[
                    {"mid": "a", "id": 1, "raw": {"type": 0}},
                    {"mid": "b", "id": 2, "raw": {"type": 0}},
                    {"mid": "c", "id": 3, "raw": {"type": 0}},
                ],
                batch_size=2,
                sleep_func=lambda _: None,
            )
            report = importer.import_targets(targets)
            self.assertEqual(report["AI·甲"]["verified_count"], 2)
            self.assertEqual(report["AI·乙"]["verified_count"], 1)
            self.assertEqual(api.add_calls, [("1", ["b"]), ("2", ["c"])])

            api.add_calls.clear()
            second = importer.import_targets(targets)
            self.assertEqual(api.add_calls, [])
            self.assertEqual(second["AI·甲"]["status"], "complete")
            self.assertEqual(second["AI·乙"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
