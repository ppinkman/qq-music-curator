import logging
import time
from datetime import datetime, timezone

from src.ai_classifier import AI_CATEGORIES
from src.qqmusic_api import QQMusicError


logger = logging.getLogger(__name__)

PLAYLIST_PREFIX = "AI\u00b7"
REVIEW_CATEGORY = "待复核"


def build_playlist_targets(songs, categories=None):
    """Build ordered, de-duplicated MID lists from stored classifications."""
    category_names = list(categories or AI_CATEGORIES)
    allowed = set(category_names)
    targets = {PLAYLIST_PREFIX + name: [] for name in category_names}
    targets[PLAYLIST_PREFIX + REVIEW_CATEGORY] = []
    seen = {name: set() for name in targets}

    for song in songs:
        mid = str(song.get("mid") or "")
        if not mid:
            continue
        classification = song.get("classification") or {}
        selected = [
            name
            for name in classification.get("categories", [])
            if name in allowed
        ]
        for category in selected:
            target_name = PLAYLIST_PREFIX + category
            if mid not in seen[target_name]:
                seen[target_name].add(mid)
                targets[target_name].append(mid)

        if classification.get("needs_review") or not selected:
            target_name = PLAYLIST_PREFIX + REVIEW_CATEGORY
            if mid not in seen[target_name]:
                seen[target_name].add(mid)
                targets[target_name].append(mid)
    return targets


class QQMusicPlaylistImporter:
    """Idempotently create AI playlists and add only missing songs."""

    def __init__(self, api, repository, songs=None, batch_size=50, sleep_func=time.sleep):
        if not 1 <= int(batch_size) <= 50:
            raise ValueError("QQ 歌单导入批次必须在 1 到 50 之间")
        self.api = api
        self.repository = repository
        self.batch_size = int(batch_size)
        self._sleep = sleep_func
        self.song_index = {}
        for song in songs or []:
            mid = str(song.get("mid") or "")
            if not mid:
                continue
            raw = song.get("raw") or {}
            self.song_index[mid] = {
                "mid": mid,
                "id": song.get("id") or raw.get("id") or raw.get("songid"),
                "type": raw.get("type", song.get("type", 0)),
            }

    def _resolve_playlists(self, target_names, state):
        remote = self.api.list_created_playlists()
        by_name = {}
        by_dirid = {}
        for playlist in remote:
            by_name.setdefault(playlist["name"], []).append(playlist)
            by_dirid[playlist["dirid"]] = playlist

        resolved = {}
        for name in target_names:
            matches = by_name.get(name, [])
            if len(matches) > 1:
                raise QQMusicError(f"发现多个同名歌单“{name}”，为避免误写已停止")
            if matches:
                playlist = matches[0]
                resolved[name] = playlist
                logger.info("复用已有歌单：%s（dirid=%s）", name, playlist["dirid"])
                continue

            previous = state["playlists"].get(name, {})
            previous_dirid = str(previous.get("dirid") or "")
            if previous.get("created_by_importer") and previous_dirid in by_dirid:
                playlist = by_dirid[previous_dirid]
                self.api.edit_playlist_name(previous_dirid, name)
                playlist = {**playlist, "name": name}
                resolved[name] = playlist
                logger.info("已恢复导入器歌单名称：%s（dirid=%s）", name, previous_dirid)
                self._sleep(0.35)
                continue

            dirid = self.api.create_playlist(name)
            playlist = {"name": name, "dirid": dirid, "tid": "", "song_count": 0}
            resolved[name] = playlist
            state["playlists"][name] = {
                "dirid": dirid,
                "created_by_importer": True,
                "status": "created",
            }
            self.repository.save_import_state(state)
            logger.info("已创建歌单：%s（dirid=%s）", name, dirid)
            self._sleep(0.35)
        return resolved

    def _add_batch_resilient(self, dirid, mids, failures):
        """Split a rejected batch so one bad song does not block the rest."""
        song_refs = []
        for mid in mids:
            song_ref = self.song_index.get(mid)
            if not song_ref or not song_ref.get("id"):
                failures[mid] = "本地记录缺少 QQ 数字歌曲 ID"
                continue
            song_refs.append(song_ref)
        if not song_refs:
            return 0
        try:
            self.api.add_songs_to_playlist(dirid, song_refs)
            return len(song_refs)
        except QQMusicError as exc:
            if len(mids) == 1:
                failures[mids[0]] = str(exc)
                return 0
            midpoint = len(mids) // 2
            left = self._add_batch_resilient(dirid, mids[:midpoint], failures)
            self._sleep(0.2)
            right = self._add_batch_resilient(dirid, mids[midpoint:], failures)
            return left + right

    def import_targets(self, targets):
        state = self.repository.load_import_state()
        state.setdefault("playlists", {})
        resolved = self._resolve_playlists(targets.keys(), state)
        report = {}

        for index, (name, desired_list) in enumerate(targets.items(), 1):
            dirid = resolved[name]["dirid"]
            desired = list(dict.fromkeys(str(mid) for mid in desired_list if mid))
            desired_set = set(desired)
            current = self.api.get_playlist_song_mids(dirid)
            missing = [mid for mid in desired if mid not in current]
            failures = {}
            attempted = 0

            logger.info(
                "[%d/%d] %s：目标 %d，已有 %d，待添加 %d",
                index,
                len(targets),
                name,
                len(desired),
                len(current & desired_set),
                len(missing),
            )

            for start in range(0, len(missing), self.batch_size):
                batch = missing[start : start + self.batch_size]
                attempted += self._add_batch_resilient(dirid, batch, failures)
                state["playlists"][name] = {
                    **state["playlists"].get(name, {}),
                    "dirid": dirid,
                    "target_count": len(desired),
                    "attempted_count": attempted,
                    "status": "adding",
                    "last_batch_end": start + len(batch),
                }
                self.repository.save_import_state(state)
                self._sleep(0.35)

            if missing:
                self._sleep(0.8)
            verified = self.api.get_playlist_song_mids(dirid)
            still_missing = [mid for mid in desired if mid not in verified]
            extra_count = len(verified - desired_set)
            status = "complete" if not still_missing else "partial"
            entry = {
                "dirid": dirid,
                "target_count": len(desired),
                "verified_count": len(desired_set & verified),
                "missing_count": len(still_missing),
                "extra_count": extra_count,
                "status": status,
                "failed_mids": still_missing,
                "errors": {mid: failures[mid] for mid in still_missing if mid in failures},
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
            state["playlists"][name] = {
                **state["playlists"].get(name, {}),
                **entry,
            }
            self.repository.save_import_state(state)
            report[name] = entry
            logger.info(
                "%s：已核验 %d/%d，缺少 %d，保留原有额外歌曲 %d",
                name,
                entry["verified_count"],
                entry["target_count"],
                entry["missing_count"],
                entry["extra_count"],
            )
        return report
