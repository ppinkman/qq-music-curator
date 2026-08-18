import unittest

from src.classifier import SongClassifier
from src.config import DEFAULT_CONFIG


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = SongClassifier(DEFAULT_CONFIG["categories"])

    def test_chinese_title_is_not_assumed_to_be_mandarin(self):
        result = self.classifier.classify_song(
            {"mid": "1", "name": "未知歌曲", "singer": "某歌手", "language": "", "genre": "", "tags": []}
        )
        self.assertEqual(result["categories"]["language"], ["未知语种"])
        self.assertTrue(result["needs_review"])

    def test_genre_and_emotion_are_separate(self):
        result = self.classifier.classify_song(
            {
                "mid": "2",
                "name": "Example",
                "singer": "Singer",
                "language": "英语",
                "genre": "流行",
                "tags": ["治愈"],
            }
        )
        self.assertEqual(result["categories"]["genre"], ["流行"])
        self.assertEqual(result["categories"]["emotion"], ["抒情"])

    def test_manual_override_has_highest_priority(self):
        classifier = SongClassifier(
            DEFAULT_CONFIG["categories"],
            {"3": {"categories": {"language": ["粤语"], "genre": [], "emotion": []}}},
        )
        result = classifier.classify_song(
            {"mid": "3", "name": "English title", "language": "英语", "genre": "", "tags": []}
        )
        self.assertEqual(result["categories"]["language"], ["粤语"])
        self.assertEqual(result["evidence"], ["manual_override"])

    def test_include_all_exclude_priority_and_casefold(self):
        classifier = SongClassifier(
            {
                "languages": {"英语": ["英语"]},
                "genres": {
                    "低优先": {"include_any": ["rock"], "priority": 1},
                    "高优先": {"include_all": ["ROCK", "LIVE"], "exclude": ["伴奏"], "priority": 10},
                },
                "emotions": {},
            }
        )
        result = classifier.classify_song(
            {"mid": "4", "name": "x", "language": "英语", "genre": "Rock Live", "tags": []}
        )
        self.assertEqual(result["categories"]["genre"], ["高优先", "低优先"])

        excluded = classifier.classify_song(
            {"mid": "5", "name": "x", "language": "英语", "genre": "Rock Live 伴奏", "tags": []}
        )
        self.assertEqual(excluded["categories"]["genre"], ["低优先"])

    def test_global_confidence_threshold_controls_review(self):
        classifier = SongClassifier(DEFAULT_CONFIG["categories"], min_confidence=0.8)
        result = classifier.classify_song(
            {"mid": "6", "name": "Example", "language": "英语", "genre": "流行", "tags": []}
        )
        self.assertEqual(result["confidence"]["overall"], 0.75)
        self.assertTrue(result["needs_review"])


if __name__ == "__main__":
    unittest.main()
