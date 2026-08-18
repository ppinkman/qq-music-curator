import tempfile
import unittest
from pathlib import Path

from src.qqmusic_api import AuthenticationError, QQMusicAPI
from src.repository import Repository


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("测试响应已耗尽")
        return self.responses.pop(0)


def favorite_payload(song_mids, total):
    return {
        "code": 0,
        "cdlist": [
            {
                "total_song_num": total,
                "songlist": [
                    {
                        "songInfo": {
                            "mid": mid,
                            "name": f"Song {mid}",
                            "singer": [{"name": "Singer"}],
                            "album": {"name": "Album"},
                        }
                    }
                    for mid in song_mids
                ],
            }
        ],
    }


def profile_payload(total):
    return {
        "code": 0,
        "data": {
            "mymusic": [
                {"id": "favorite-playlist", "title": "我喜欢", "type": 1, "num0": total}
            ]
        },
    }


class QQMusicAPITests(unittest.TestCase):
    def test_cookie_initialization_extracts_uin(self):
        api = QQMusicAPI(
            cookie_str="foo=bar; uin=o0012345; p_skey=secret",
            session=FakeSession([]),
            sleep_func=lambda _: None,
        )
        self.assertEqual(api.user_uin, "12345")
        self.assertNotEqual(api.get_g_tk(), 5381)

    def test_validate_login_rejects_cookie_without_uin(self):
        api = QQMusicAPI(
            cookie_str="p_skey=secret",
            session=FakeSession([]),
            sleep_func=lambda _: None,
        )
        with self.assertRaises(AuthenticationError):
            api.validate_login()

    def test_multi_page_fetch_deduplicates_and_completes_checkpoint(self):
        session = FakeSession(
            [
                FakeResponse(profile_payload(total=3)),
                FakeResponse(favorite_payload(["a", "b"], total=3)),
                FakeResponse(favorite_payload(["b", "c"], total=3)),
            ]
        )
        api = QQMusicAPI(
            cookie_str="uin=o00123; p_skey=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            songs = api.get_favorite_songs(page_size=2, repository=repo)
            self.assertEqual([song["mid"] for song in songs], ["a", "b", "c"])
            checkpoint = repo.load_checkpoint()
            self.assertTrue(checkpoint["complete"])
            self.assertEqual(checkpoint["next_begin"], 0)
            self.assertEqual(len(repo.load_songs()), 3)

    def test_resume_merges_existing_songs_instead_of_overwriting(self):
        session = FakeSession(
            [FakeResponse(profile_payload(total=3)), FakeResponse(favorite_payload(["c"], total=3))]
        )
        api = QQMusicAPI(
            cookie_str="uin=o00123; p_skey=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            repo.save_songs(
                [
                    {"mid": "a", "name": "Song a", "singer": "Singer"},
                    {"mid": "b", "name": "Song b", "singer": "Singer"},
                ]
            )
            songs = api.get_favorite_songs(
                start_begin=2,
                page_size=2,
                repository=repo,
            )
            self.assertEqual([song["mid"] for song in songs], ["a", "b", "c"])

    def test_full_refresh_removes_songs_no_longer_returned(self):
        session = FakeSession(
            [FakeResponse(profile_payload(total=1)), FakeResponse(favorite_payload(["a"], total=1))]
        )
        api = QQMusicAPI(
            cookie_str="uin=o00123; p_skey=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            repo.save_songs(
                [
                    {"mid": "a", "name": "Song a", "singer": "Singer"},
                    {"mid": "removed", "name": "Removed", "singer": "Singer"},
                ]
            )
            songs = api.get_favorite_songs(page_size=2, repository=repo)
            self.assertEqual([song["mid"] for song in songs], ["a"])
            self.assertEqual([song["mid"] for song in repo.load_songs()], ["a"])

    def test_song_parser_handles_legacy_shape(self):
        song = QQMusicAPI._parse_song_item(
            {
                "songmid": "legacy",
                "songname": "Old Song",
                "singername": "Old Singer",
                "albumname": "Old Album",
            }
        )
        self.assertEqual(song["mid"], "legacy")
        self.assertEqual(song["singer"], "Old Singer")
        self.assertEqual(song["album"], "Old Album")

    def test_validate_login_uses_profile_favorite_playlist(self):
        session = FakeSession([FakeResponse(profile_payload(total=10))])
        api = QQMusicAPI(
            cookie_str="uin=o00123; qm_keyst=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        api.validate_login()
        self.assertEqual(api._favorite_playlist_id, "favorite-playlist")
        self.assertEqual(api._favorite_playlist_total, 10)

    def test_song_detail_extracts_release_date(self):
        payload = {
            "songinfo": {
                "code": 0,
                "data": {
                    "track_info": {"language": 2, "time_public": "2004-06-01"},
                    "info": {},
                },
            }
        }
        api = QQMusicAPI(
            session=FakeSession([FakeResponse(payload)]),
            sleep_func=lambda _: None,
        )
        detail = api.get_song_detail("mid")
        self.assertEqual(detail["release_date"], "2004-06-01")

    def test_list_created_playlists_normalizes_fields(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "code": 0,
                        "data": {
                            "disslist": [
                                {
                                    "diss_name": "AI·测试",
                                    "dirid": 12,
                                    "tid": 34,
                                    "song_cnt": 5,
                                    "dir_show": 1,
                                }
                            ]
                        },
                    }
                )
            ]
        )
        api = QQMusicAPI(
            cookie_str="uin=o00123; p_skey=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        self.assertEqual(
            api.list_created_playlists(),
            [
                {
                    "name": "AI·测试",
                    "dirid": "12",
                    "tid": "34",
                    "song_count": 5,
                    "visible": True,
                }
            ],
        )

    def test_add_songs_sends_mid_and_type_lists(self):
        session = FakeSession(
            [FakeResponse({"req_0": {"code": 0, "data": {"retCode": 0}}})]
        )
        api = QQMusicAPI(
            cookie_str="uin=o00123; p_skey=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        songs = [
            {"mid": "a", "id": 10, "type": 0},
            {"mid": "b", "id": 11, "type": 1},
        ]
        self.assertEqual(api.add_songs_to_playlist("9", songs), 2)
        method, _, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        request = kwargs["json"]["req_0"]
        self.assertEqual(request["method"], "AddSonglist")
        self.assertEqual(request["param"]["dirId"], 9)
        self.assertEqual(
            request["param"]["v_songInfo"],
            [{"songId": 10, "songType": 0}, {"songId": 11, "songType": 1}],
        )

    def test_create_playlist_returns_dirid(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "req_0": {
                            "code": 0,
                            "data": {"result": {"dirId": 88}},
                        }
                    }
                )
            ]
        )
        api = QQMusicAPI(
            cookie_str="uin=o00123; p_skey=secret",
            session=session,
            sleep_func=lambda _: None,
        )
        self.assertEqual(api.create_playlist("AI·测试"), "88")
        method, _, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(kwargs["json"]["req_0"]["param"]["dirName"], "AI·测试")


if __name__ == "__main__":
    unittest.main()
