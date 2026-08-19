import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Repository:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.songs_file = os.path.join(self.data_dir, "songs.jsonl")
        self.metadata_cache_file = os.path.join(self.data_dir, "metadata_cache.jsonl")
        self.checkpoint_file = os.path.join(self.data_dir, "checkpoint.json")
        self.overrides_file = os.path.join(self.data_dir, "overrides.json")
        self.failures_file = os.path.join(self.data_dir, "failures.jsonl")

    @staticmethod
    def _atomic_write_text(path, text):
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)

    @staticmethod
    def _read_jsonl(path):
        if not os.path.exists(path):
            return []
        items = []
        with open(path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("忽略损坏的 JSONL 行：%s:%d", path, line_number)
                    continue
                if isinstance(item, dict):
                    items.append(item)
        return items

    @staticmethod
    def _jsonl_text(items):
        return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)

    def save_songs(self, songs):
        """按 mid 保留首次出现顺序，后出现记录覆盖字段。"""
        order = []
        by_mid = {}
        for song in songs:
            mid = str(song.get("mid", ""))
            if not mid:
                continue
            if mid not in by_mid:
                order.append(mid)
                by_mid[mid] = {}
            by_mid[mid].update(song)
            by_mid[mid]["mid"] = mid
        unique_songs = [by_mid[mid] for mid in order]
        self._atomic_write_text(self.songs_file, self._jsonl_text(unique_songs))
        logger.info("已持久化 %d 首歌曲至 %s", len(unique_songs), self.songs_file)

    def load_songs(self):
        return self._read_jsonl(self.songs_file)

    def load_metadata_cache(self):
        cache = {}
        for item in self._read_jsonl(self.metadata_cache_file):
            mid = str(item.get("mid", ""))
            if mid:
                cache[mid] = item
        return cache

    def save_metadata_item(self, song_mid, detail):
        """按 mid 原子更新详情缓存，避免重复追加和半行数据。"""
        self.save_metadata_items({str(song_mid): detail})

    def save_metadata_items(self, items):
        """批量更新详情缓存，减少大歌单下的重复磁盘写入。"""
        cache = self.load_metadata_cache()
        for song_mid, detail in items.items():
            item = dict(detail)
            item["mid"] = str(song_mid)
            cache[str(song_mid)] = item
        self._atomic_write_text(self.metadata_cache_file, self._jsonl_text(cache.values()))

    def save_checkpoint(self, next_begin, total, fetched_count, complete=False):
        checkpoint = {
            "next_begin": int(next_begin),
            "total": int(total or 0),
            "fetched_count": int(fetched_count),
            "complete": bool(complete),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write_text(
            self.checkpoint_file,
            json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
        )

    def load_checkpoint(self):
        default = {"next_begin": 0, "total": 0, "fetched_count": 0, "complete": False}
        if not os.path.exists(self.checkpoint_file):
            return default
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as handle:
                checkpoint = json.load(handle)
            if not isinstance(checkpoint, dict):
                return default
            # 兼容旧版 begin 字段。
            if "next_begin" not in checkpoint:
                checkpoint["next_begin"] = checkpoint.get("begin", 0)
            return {**default, **checkpoint}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取检查点失败，将从头开始：%s", exc)
            return default

    def load_overrides(self):
        if not os.path.exists(self.overrides_file):
            return {}
        try:
            with open(self.overrides_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取人工覆盖规则失败：%s", exc)
            return {}

    def load_failures(self):
        latest = {}
        for item in self._read_jsonl(self.failures_file):
            mid = str(item.get("mid", ""))
            if mid:
                latest[mid] = item
        return list(latest.values())

    def replace_failures(self, failures):
        self._atomic_write_text(self.failures_file, self._jsonl_text(failures))

    def log_failure(self, song_mid, reason="", operation="metadata"):
        failures = {item["mid"]: item for item in self.load_failures() if item.get("mid")}
        mid = str(song_mid)
        failures[mid] = {
            "mid": mid,
            "operation": operation,
            "reason": str(reason),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.replace_failures(failures.values())
