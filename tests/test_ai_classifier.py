import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.ai_classifier import (
    AI_CATEGORIES,
    BatchDecision,
    OpenAIMusicClassifier,
)
from src.exporter import PlaylistExporter
from src.repository import Repository


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self, parsed):
        self.responses = FakeResponses(parsed)


class AIClassifierTests(unittest.TestCase):
    def test_batch_input_ignores_qq_labels_and_normalizes_results(self):
        parsed = BatchDecision.model_validate(
            {
                "songs": [
                    {
                        "mid": "m1",
                        "categories": [
                            {"category": "华语女声", "confidence": 0.94, "reason": "华语女性独唱"},
                            {"category": "深夜情绪", "confidence": 0.62, "reason": "氛围克制"},
                        ],
                        "uncertain": False,
                        "uncertainty_reason": "",
                    }
                ]
            }
        )
        client = FakeClient(parsed)
        classifier = OpenAIMusicClassifier(client=client, min_confidence=0.7)
        results = classifier.classify_batch(
            [
                {
                    "mid": "m1",
                    "name": "Song",
                    "singer": "Singer",
                    "album": "Album",
                    "release_date": "2003-01-01",
                    "language": "恶意标签",
                    "genre": "恶意曲风",
                    "tags": ["恶意情绪"],
                }
            ]
        )

        user_payload = client.responses.calls[0]["input"][1]["content"]
        self.assertNotIn("恶意标签", user_payload)
        self.assertNotIn("恶意曲风", user_payload)
        self.assertNotIn("恶意情绪", user_payload)
        self.assertEqual(json.loads(user_payload)["songs"][0]["release_date"], "2003-01-01")
        self.assertEqual(results["m1"]["categories"], ["华语女声"])
        self.assertEqual(results["m1"]["confidence"]["by_category"]["深夜情绪"], 0.62)

    def test_uncertain_or_unmatched_song_needs_review(self):
        parsed = BatchDecision.model_validate(
            {
                "songs": [
                    {
                        "mid": "m2",
                        "categories": [],
                        "uncertain": True,
                        "uncertainty_reason": "不认识该作品",
                    }
                ]
            }
        )
        result = OpenAIMusicClassifier(client=FakeClient(parsed)).classify_batch(
            [{"mid": "m2", "name": "Unknown", "singer": "Unknown"}]
        )["m2"]
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["categories"], [])

    def test_repository_cache_is_scoped_by_model_and_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(directory)
            repo.save_ai_items(
                {
                    "m1": {
                        "categories": ["华语女声"],
                        "model": "model-a",
                        "prompt_version": "p1",
                    }
                }
            )
            self.assertIn("m1", repo.load_ai_cache(model="model-a", prompt_version="p1"))
            self.assertNotIn("m1", repo.load_ai_cache(model="model-b", prompt_version="p1"))
            repo.clear_ai_cache(model="model-a", prompt_version="p1")
            self.assertNotIn("m1", repo.load_ai_cache(model="model-a", prompt_version="p1"))

    def test_exporter_only_writes_fixed_ai_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            playlists = Path(directory) / "playlists"
            playlists.mkdir(parents=True)
            (playlists / "普通话.txt").write_text("旧结果", encoding="utf-8")
            songs = [
                {
                    "mid": "m1",
                    "name": "Song",
                    "singer": "Singer",
                    "album": "Album",
                    "classification": {
                        "categories": ["华语女声", "深夜情绪", "非法分类"],
                        "confidence": {"overall": 0.9},
                        "evidence": ["ai:test"],
                        "needs_review": False,
                    },
                }
            ]
            PlaylistExporter(directory, categories=AI_CATEGORIES).export_all(songs)
            filenames = {path.name for path in playlists.glob("*.txt")}
            self.assertEqual(filenames, {f"{name}.txt" for name in AI_CATEGORIES})
            self.assertIn("Song - Singer", (playlists / "华语女声.txt").read_text(encoding="utf-8"))
            self.assertFalse((playlists / "普通话.txt").exists())


if __name__ == "__main__":
    unittest.main()
