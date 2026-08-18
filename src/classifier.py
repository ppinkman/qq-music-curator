import re


CANTONESE_CHAR_REGEX = re.compile(r"[佢喺啲乜睇冇唔嘢搵咗哋靓講聽係嘅啱睏囉抁]")
JAPANESE_CHAR_REGEX = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
KOREAN_CHAR_REGEX = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")


class SongClassifier:
    def __init__(self, config_categories=None, overrides=None, min_confidence=0.7):
        self.categories_config = config_categories or {}
        self.overrides = overrides or {}
        self.min_confidence = float(min_confidence)
        self.lang_config = self.categories_config.get("languages", {})
        self.genre_config = self.categories_config.get("genres", {})
        self.emotion_config = self.categories_config.get("emotions", {})

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value if str(item)]

    def _parse_rule(self, rule, default_confidence):
        if isinstance(rule, list):
            return {"include_any": self._as_list(rule), "include_all": [], "exclude": [], "priority": 0, "confidence": default_confidence}
        if isinstance(rule, dict):
            return {
                "include_any": self._as_list(rule.get("include_any")),
                "include_all": self._as_list(rule.get("include_all")),
                "exclude": self._as_list(rule.get("exclude")),
                "priority": int(rule.get("priority", 0)),
                "confidence": float(rule.get("min_confidence", default_confidence)),
            }
        return {"include_any": [], "include_all": [], "exclude": [], "priority": 0, "confidence": default_confidence}

    @staticmethod
    def _contains(text, keyword):
        return keyword.casefold() in text.casefold()

    def _match_dimension(self, rules, text, dimension, default_confidence):
        matches = []
        for category_name, raw_rule in rules.items():
            rule = self._parse_rule(raw_rule, default_confidence)
            if any(self._contains(text, word) for word in rule["exclude"]):
                continue
            any_hits = [word for word in rule["include_any"] if self._contains(text, word)]
            all_hits = [word for word in rule["include_all"] if self._contains(text, word)]
            any_ok = not rule["include_any"] or bool(any_hits)
            all_ok = len(all_hits) == len(rule["include_all"])
            if not ((rule["include_any"] or rule["include_all"]) and any_ok and all_ok):
                continue
            evidence_words = list(dict.fromkeys(any_hits + all_hits))
            matches.append({
                "name": category_name,
                "priority": rule["priority"],
                "confidence": rule["confidence"],
                "evidence": [f"metadata_{dimension}:{word}" for word in evidence_words],
            })
        matches.sort(key=lambda match: (-match["priority"], match["name"]))
        return matches

    def classify_song(self, song):
        song_mid = str(song.get("mid", ""))
        if song_mid in self.overrides:
            override_data = self.overrides[song_mid]
            categories = override_data.get("categories", override_data)
            normalized = {
                "language": self._as_list(categories.get("language")),
                "genre": self._as_list(categories.get("genre")),
                "emotion": self._as_list(categories.get("emotion")),
            }
            return {
                "categories": normalized,
                "confidence": {"language": 1.0, "genre": 1.0, "emotion": 1.0, "overall": 1.0},
                "evidence": ["manual_override"],
                "needs_review": False,
            }

        language_text = str(song.get("language", ""))
        genre_text = str(song.get("genre", ""))
        tags_text = " ".join(self._as_list(song.get("tags")))
        song_name = str(song.get("name", ""))
        full_title = f"{song_name} {song.get('singer', '')}"

        language_matches = self._match_dimension(self.lang_config, f"{language_text} {tags_text}", "language", 0.8)
        genre_matches = self._match_dimension(self.genre_config, f"{genre_text} {tags_text}", "genre", 0.7)
        emotion_matches = self._match_dimension(self.emotion_config, f"{genre_text} {tags_text}", "emotion", 0.6)

        evidence = []
        for match in language_matches + genre_matches + emotion_matches:
            evidence.extend(match["evidence"])

        language_confidence = max((match["confidence"] for match in language_matches), default=0.0)
        if not language_matches:
            inferred, language_confidence, inferred_evidence = self._infer_language(full_title, song_name)
            language_matches = [{"name": inferred}]
            evidence.append(inferred_evidence)

        genre_confidence = max((match["confidence"] for match in genre_matches), default=0.0)
        emotion_confidence = max((match["confidence"] for match in emotion_matches), default=0.0)
        overall_confidence = round((language_confidence + (genre_confidence or 0.4)) / 2.0, 2)
        categories = {
            "language": [match["name"] for match in language_matches],
            "genre": [match["name"] for match in genre_matches],
            "emotion": [match["name"] for match in emotion_matches],
        }
        return {
            "categories": categories,
            "confidence": {
                "language": language_confidence,
                "genre": genre_confidence,
                "emotion": emotion_confidence,
                "overall": overall_confidence,
            },
            "evidence": list(dict.fromkeys(evidence)),
            "needs_review": "未知语种" in categories["language"] or overall_confidence < self.min_confidence,
        }

    def _infer_language(self, full_title, song_name):
        if JAPANESE_CHAR_REGEX.search(full_title):
            return "日语", 0.85, "heuristic:japanese_kana"
        if KOREAN_CHAR_REGEX.search(full_title):
            return "韩语", 0.85, "heuristic:korean_hangul"
        if CANTONESE_CHAR_REGEX.search(full_title):
            return "粤语", 0.8, "heuristic:cantonese_char"
        if self._is_mostly_english(song_name):
            return "英语", 0.75, "heuristic:english_text"
        return "未知语种", 0.3, "fallback:unknown_language"

    @staticmethod
    def _is_mostly_english(text):
        text_clean = re.sub(r"[\s\d\W_]", "", text)
        if not text_clean:
            return False
        english_chars = sum(1 for char in text_clean if "a" <= char.lower() <= "z")
        return (english_chars / len(text_clean)) > 0.8
