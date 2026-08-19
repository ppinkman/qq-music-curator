import logging
import random
import re
import time

import requests

logger = logging.getLogger(__name__)


LANGUAGE_ID_MAP = {
    0: "国语",
    1: "粤语",
    2: "英语",
    3: "日语",
    4: "韩语",
    5: "闽南语",
    6: "法语",
    7: "西班牙语",
    8: "其它",
}


class QQMusicError(RuntimeError):
    """QQ 音乐访问的基础异常。"""


class AuthenticationError(QQMusicError):
    """登录凭据缺失或服务端明确拒绝登录态。"""


class APIResponseError(QQMusicError):
    """网络正常，但返回状态或数据结构不符合预期。"""


class QQMusicAPI:
    MUSICU_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
    PROFILE_URL = "https://c6.y.qq.com/rsc/fcgi-bin/fcg_get_profile_homepage.fcg"
    PLAYLIST_DETAIL_URL = "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"
    FAVORITE_FALLBACK_URL = "https://c.y.qq.com/v8/fcg-bin/fcg_v8_user_discomusic.fcg"

    def __init__(
        self,
        cookie_str="",
        user_uin="",
        session=None,
        timeout=10,
        max_retries=3,
        sleep_func=time.sleep,
    ):
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://y.qq.com/",
                "Origin": "https://y.qq.com",
            }
        )
        self.user_uin = ""
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries))
        self._sleep = sleep_func
        self._favorite_playlist_id = ""
        self._favorite_playlist_total = 0

        if cookie_str:
            self.set_cookie(cookie_str)
        if user_uin:
            self.user_uin = str(user_uin).lstrip("o0") or "0"

    def set_cookie(self, cookie_str):
        self.session.headers.update({"Cookie": cookie_str})
        extracted = self._extract_uin_from_cookie(cookie_str)
        if extracted:
            self.user_uin = extracted

    @staticmethod
    def _extract_uin_from_cookie(cookie_str):
        """从 Cookie 中提取 uin / wxuin / qq / luin。"""
        match = re.search(
            r"(?:^|;\s*)(?:uin|wxuin|luin|qq)=o?0*(\d+)",
            cookie_str or "",
            re.IGNORECASE,
        )
        return match.group(1) if match else ""

    def get_g_tk(self):
        """根据 p_skey / skey 计算 g_tk。"""
        cookie = self.session.headers.get("Cookie", "")
        p_skey_match = re.search(r"(?:^|;\s*)p_skey=([^;]+)", cookie)
        skey_match = re.search(r"(?:^|;\s*)skey=@?([^;]+)", cookie)
        skey = (
            p_skey_match.group(1)
            if p_skey_match
            else (skey_match.group(1) if skey_match else "")
        )

        hash_val = 5381
        for char in skey:
            hash_val += (hash_val << 5) + ord(char)
        return hash_val & 0x7FFFFFFF

    def _request_json(self, method, url, **kwargs):
        """执行有限重试的 JSON 请求，不在异常中暴露请求头或 Cookie。"""
        last_error = None
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code in (401, 403):
                    raise AuthenticationError(f"服务端拒绝登录态（HTTP {response.status_code}）")
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.RequestException(f"HTTP {response.status_code}")
                if response.status_code != 200:
                    raise APIResponseError(f"QQ 音乐接口返回 HTTP {response.status_code}")
                try:
                    # Some legacy QQ Music endpoints send UTF-8 JSON while requests
                    # interprets the non-standard `charset:utf8` header as Latin-1.
                    if (
                        getattr(response, "encoding", None) == "ISO-8859-1"
                        and "utf8" in str(getattr(response, "headers", {}).get("content-type", "")).lower()
                    ):
                        response.encoding = "utf-8"
                    return response.json()
                except (TypeError, ValueError) as exc:
                    raise APIResponseError("QQ 音乐接口未返回有效 JSON") from exc
            except AuthenticationError:
                raise
            except APIResponseError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = min(4.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.15)
                    logger.warning("QQ 音乐请求失败，%.1f 秒后重试（%d/%d）", delay, attempt, self.max_retries)
                    self._sleep(delay)

        raise QQMusicError(f"QQ 音乐网络请求连续失败（已重试 {self.max_retries} 次）") from last_error

    @staticmethod
    def _module_data(payload, module_name):
        module = payload.get(module_name)
        if not isinstance(module, dict):
            raise APIResponseError(f"响应缺少模块 {module_name}，接口结构可能已变化")

        code = module.get("code", 0)
        if code not in (0, None):
            message = module.get("msg") or module.get("message") or "服务端拒绝请求"
            if code in (1000, 1001, 2000, 2001, 3000):
                raise AuthenticationError(f"登录态无效（code={code}）：{message}")
            raise APIResponseError(f"接口业务错误（code={code}）：{message}")

        data = module.get("data")
        if not isinstance(data, dict):
            raise APIResponseError(f"模块 {module_name} 缺少 data，接口结构可能已变化")
        return data

    def _favorite_request_body(self, begin, num):
        return {
            "comm": {"ct": 24, "cv": 0},
            "fav_list": {
                "module": "music.musicfav.MusicFavListList",
                "method": "GetSongList",
                "param": {
                    "dirid": 201,
                    "stype": 0,
                    "order": 1,
                    "begin": begin,
                    "num": num,
                    "uin": int(self.user_uin) if self.user_uin.isdigit() else 0,
                },
            },
        }

    def _fetch_favorite_page_legacy_musicu(self, begin, num):
        payload = self._request_json(
            "POST",
            self.MUSICU_URL,
            json=self._favorite_request_body(begin, num),
        )
        data = self._module_data(payload, "fav_list")
        song_list = data.get("songlist", [])
        if not isinstance(song_list, list):
            raise APIResponseError("fav_list.data.songlist 不是列表")
        total = data.get("total_num", data.get("total", 0))
        try:
            total = int(total or 0)
        except (TypeError, ValueError):
            total = 0
        return song_list, total

    def _get_favorite_playlist_info(self):
        """从用户主页解析当前账号的“我喜欢”歌单 ID。"""
        if self._favorite_playlist_id:
            return self._favorite_playlist_id, self._favorite_playlist_total

        payload = self._request_json(
            "GET",
            self.PROFILE_URL,
            params={
                "cid": 205360838,
                "userid": self.user_uin,
                "reqfrom": 1,
                "format": "json",
            },
        )
        code = payload.get("code", 0) if isinstance(payload, dict) else None
        if code in (1000, 1001, 2000, 2001, 3000):
            raise AuthenticationError(f"用户主页拒绝登录态（code={code}）")
        if code not in (0, None):
            raise APIResponseError(f"用户主页接口业务错误（code={code}）")

        data = payload.get("data") if isinstance(payload, dict) else None
        my_music = data.get("mymusic", []) if isinstance(data, dict) else []
        if not isinstance(my_music, list):
            raise APIResponseError("用户主页响应中的 mymusic 不是列表")

        favorite = next(
            (
                item
                for item in my_music
                if isinstance(item, dict)
                and (item.get("type") == 1 or item.get("title") == "我喜欢")
                and item.get("id")
            ),
            None,
        )
        if not favorite:
            raise APIResponseError("用户主页中未找到“我喜欢”歌单")

        self._favorite_playlist_id = str(favorite["id"])
        try:
            self._favorite_playlist_total = int(favorite.get("num0") or 0)
        except (TypeError, ValueError):
            self._favorite_playlist_total = 0
        return self._favorite_playlist_id, self._favorite_playlist_total

    def _fetch_favorite_page(self, begin, num):
        """使用主页返回的歌单 ID，通过歌单详情接口分页读取。"""
        playlist_id, profile_total = self._get_favorite_playlist_info()
        payload = self._request_json(
            "GET",
            self.PLAYLIST_DETAIL_URL,
            params={
                "type": 1,
                "utf8": 1,
                "disstid": playlist_id,
                "loginUin": self.user_uin,
                "hostUin": 0,
                "format": "json",
                "inCharset": "utf8",
                "outCharset": "utf-8",
                "notice": 0,
                "platform": "yqq.json",
                "needNewCode": 0,
                "song_begin": begin,
                "song_num": num,
            },
        )
        code = payload.get("code", 0) if isinstance(payload, dict) else None
        if code in (1000, 1001, 2000, 2001, 3000):
            raise AuthenticationError(f"歌单详情接口拒绝登录态（code={code}）")
        if code not in (0, None):
            raise APIResponseError(f"歌单详情接口业务错误（code={code}）")

        cd_list = payload.get("cdlist") if isinstance(payload, dict) else None
        if not isinstance(cd_list, list) or not cd_list or not isinstance(cd_list[0], dict):
            raise APIResponseError("歌单详情响应缺少 cdlist")
        playlist = cd_list[0]
        song_list = playlist.get("songlist", [])
        if not isinstance(song_list, list):
            raise APIResponseError("歌单详情中的 songlist 不是列表")

        total = playlist.get("total_song_num", playlist.get("songnum", profile_total))
        try:
            total = int(total or profile_total or 0)
        except (TypeError, ValueError):
            total = profile_total
        return song_list, total

    def validate_login(self):
        """验证凭据字段，并确认当前用户的“我喜欢”歌单可访问。"""
        if not self.session.headers.get("Cookie"):
            raise AuthenticationError("未设置 Cookie")
        if not self.user_uin:
            raise AuthenticationError("Cookie 中未找到 uin/wxuin，请重新复制完整 Cookie")
        self._get_favorite_playlist_info()

    def test_login(self):
        """兼容旧调用方式，返回 (是否成功, 可读信息)。"""
        try:
            self.validate_login()
            return True, "登录态验证成功"
        except AuthenticationError as exc:
            return False, str(exc)
        except QQMusicError as exc:
            return False, f"接口或网络异常：{exc}"

    def get_favorite_songs(self, limit=5000, start_begin=0, page_size=100, repository=None):
        """分页读取“我喜欢”；每页落盘，支持从检查点继续。"""
        if limit <= 0 or page_size <= 0:
            raise ValueError("limit 和 page_size 必须大于 0")

        # 从 0 开始代表一次完整刷新；从非零 offset 开始才合并已有检查点数据。
        songs = repository.load_songs() if repository and start_begin > 0 else []
        seen_mids = {song.get("mid") for song in songs if song.get("mid")}
        begin = max(0, int(start_begin))
        total_num = 0
        page_signatures = set()
        fetched_this_run = 0

        logger.info("开始拉取“我喜欢”歌单数据（起始 offset=%d）", begin)

        while fetched_this_run < limit:
            request_size = min(page_size, limit - fetched_this_run)
            try:
                song_list, page_total = self._fetch_favorite_page(begin, request_size)
            except AuthenticationError:
                raise
            except QQMusicError as primary_error:
                logger.warning("歌单详情接口读取第 %d 页失败，尝试旧版 musicu 接口", begin // page_size + 1)
                try:
                    song_list, page_total = self._fetch_favorite_page_legacy_musicu(begin, request_size)
                except QQMusicError:
                    logger.warning("旧版 musicu 接口不可用，尝试最旧版收藏接口")
                    try:
                        song_list, page_total = self._get_favorite_songs_fallback(begin, request_size)
                    except QQMusicError as fallback_error:
                        raise QQMusicError("三条只读接口均无法读取“我喜欢”歌单") from fallback_error
                logger.debug("歌单详情接口失败原因：%s", type(primary_error).__name__)

            if page_total > 0:
                total_num = page_total

            page_items = []
            page_mids = []
            for item in song_list:
                song_info = self._parse_song_item(item)
                if not song_info:
                    continue
                page_items.append(song_info)
                page_mids.append(song_info["mid"])
                if song_info["mid"] not in seen_mids:
                    seen_mids.add(song_info["mid"])
                    songs.append(song_info)

            signature = tuple(page_mids)
            if signature and signature in page_signatures:
                raise APIResponseError("接口重复返回同一页，已停止以避免无限循环")
            if signature:
                page_signatures.add(signature)

            fetched_this_run += len(song_list)
            next_begin = begin + len(song_list)
            complete = (
                not song_list
                or (total_num > 0 and next_begin >= total_num)
                or len(song_list) < request_size
            )

            if repository:
                repository.save_songs(songs)
                repository.save_checkpoint(
                    next_begin=0 if complete else next_begin,
                    total=total_num,
                    fetched_count=len(songs),
                    complete=complete,
                )

            logger.info(
                "读取 offset=%d：返回 %d 条、解析 %d 条，当前本地共 %d / %s",
                begin,
                len(song_list),
                len(page_items),
                len(songs),
                total_num or "未知",
            )

            if complete:
                break
            begin = next_begin
            self._sleep(0.3)

        return songs

    def _get_favorite_songs_fallback(self, begin=0, num=100):
        params = {
            "cid": "205360956",
            "cv": "4747474",
            "ct": "24",
            "stype": "0",
            "order": "1",
            "begin": begin,
            "num": num,
            "dirid": "201",
            "uin": self.user_uin,
            "g_tk": self.get_g_tk(),
            "format": "json",
        }
        payload = self._request_json("GET", self.FAVORITE_FALLBACK_URL, params=params)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise APIResponseError("备用接口响应缺少 data")
        song_list = data.get("songlist", [])
        if not isinstance(song_list, list):
            raise APIResponseError("备用接口 songlist 不是列表")
        total = data.get("total", data.get("total_num", 0))
        try:
            total = int(total or 0)
        except (TypeError, ValueError):
            total = 0
        return song_list, total

    @staticmethod
    def _parse_song_item(item):
        if not isinstance(item, dict):
            return None
        track = item.get("songInfo", item)
        if not isinstance(track, dict):
            return None

        song_mid = track.get("mid") or track.get("songmid")
        song_name = track.get("name") or track.get("songname", "")
        if not song_mid:
            return None

        singers = track.get("singer", [])
        singer_names = [
            singer.get("name", "")
            for singer in singers
            if isinstance(singer, dict) and singer.get("name")
        ]
        singer_str = "/".join(singer_names) if singer_names else track.get("singername", "未知歌手")

        album = track.get("album", {})
        album_name = album.get("name", "") if isinstance(album, dict) else ""
        return {
            "id": track.get("id") or track.get("songid"),
            "mid": str(song_mid),
            "name": song_name,
            "singer": singer_str,
            "album": album_name or track.get("albumname", ""),
            "language_id": track.get("language"),
            "genre_id": track.get("genre"),
            "raw": track,
        }

    def get_song_detail(self, song_mid):
        """获取单曲详情；失败时抛出 QQMusicError，由调用方记录重试。"""
        body = {
            "comm": {"ct": 24, "cv": 0},
            "songinfo": {
                "module": "music.pf_song_detail_svr",
                "method": "get_song_detail_yqq",
                "param": {"song_mid": song_mid},
            },
        }
        payload = self._request_json("POST", self.MUSICU_URL, json=body)
        data = self._module_data(payload, "songinfo")
        track_info = data.get("track_info", {})
        info_list = data.get("info", {})

        language_name = ""
        genre_name = ""
        tags = []
        if isinstance(info_list, dict):
            for value in info_list.values():
                if not isinstance(value, dict):
                    continue
                title = value.get("title", "")
                content = [
                    item.get("value", "")
                    for item in value.get("content", [])
                    if isinstance(item, dict) and item.get("value")
                ]
                if title == "语种":
                    language_name = "/".join(content)
                elif title in ("流派", "风格"):
                    genre_name = "/".join(content)
                elif title in ("标签", "情感", "场景"):
                    tags.extend(content)

        if not language_name and isinstance(track_info, dict):
            language_id = track_info.get("language")
            if isinstance(language_id, int):
                language_name = LANGUAGE_ID_MAP.get(language_id, "")

        return {
            "mid": str(song_mid),
            "language": language_name,
            "genre": genre_name,
            "tags": list(dict.fromkeys(tags)),
            "release_date": (
                str(track_info.get("time_public", ""))
                if isinstance(track_info, dict)
                else ""
            ),
        }
