import os
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config.json"
COOKIE_FILE_PATH = "cookie.txt"

DEFAULT_CONFIG = {
    "categories": {
        "languages": {
            "普通话": {"include_any": ["国语", "普通话", "华语"], "min_confidence": 0.8},
            "粤语": {"include_any": ["粤语"], "min_confidence": 0.8},
            "英语": {"include_any": ["英语", "欧美"], "min_confidence": 0.8},
            "日语": {"include_any": ["日语"], "min_confidence": 0.8},
            "韩语": {"include_any": ["韩语"], "min_confidence": 0.8}
        },
        "genres": {
            "流行": {"include_any": ["流行", "Pop"], "min_confidence": 0.7},
            "摇滚": {"include_any": ["摇滚", "重金属", "朋克"], "min_confidence": 0.7},
            "民谣": {"include_any": ["民谣", "乡村"], "min_confidence": 0.7},
            "电子": {"include_any": ["电子", "Electropop", "EDM", "舞曲"], "min_confidence": 0.7},
            "R&B": {"include_any": ["R&B", "灵魂", "Funk"], "min_confidence": 0.7},
            "嘻哈": {"include_any": ["嘻哈", "Hip-Hop", "Rap", "说唱"], "min_confidence": 0.7},
            "轻音乐": {"include_any": ["轻音乐", "纯音乐", "古典", "钢琴"], "min_confidence": 0.7}
        },
        "emotions": {
            "抒情": {"include_any": ["抒情", "伤感", "安静", "治愈", "慢歌"], "min_confidence": 0.6},
            "热血": {"include_any": ["热血", "激昂", "燃", "运动"], "min_confidence": 0.6}
        }
    },
    "min_confidence": 0.7,
    "output_dir": "output",
    "data_dir": "data",
}

class AppConfig:
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.raw_config = self._load_json_config()
        self.cookie = self._resolve_cookie()
        self.user_uin = str(self.raw_config.get("user_uin", ""))
        self.categories = self._merge_categories(self.raw_config.get("categories", {}))
        self.min_confidence = self.raw_config.get("min_confidence", 0.7)
        self.output_dir = self.raw_config.get("output_dir", "output")
        self.data_dir = self.raw_config.get("data_dir", "data")

    @staticmethod
    def _merge_categories(configured):
        """保留用户规则，并补上缺失的分类维度。"""
        merged = {}
        for dimension, defaults in DEFAULT_CONFIG["categories"].items():
            custom = configured.get(dimension) if isinstance(configured, dict) else None
            merged[dimension] = custom if isinstance(custom, dict) else defaults
        return merged

    def _load_json_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"读取配置文件 {self.config_path} 失败: {e}，将使用默认配置")
        return DEFAULT_CONFIG

    def _resolve_cookie(self):
        # 1. 优先读取环境变量
        env_cookie = os.getenv("QQMUSIC_COOKIE", "").strip()
        if env_cookie:
            logger.info("已从环境变量 QQMUSIC_COOKIE 读取登录凭据")
            return env_cookie

        # 2. 其次读取 cookie.txt
        if os.path.exists(COOKIE_FILE_PATH):
            try:
                with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                    file_cookie = f.read().strip()
                    if file_cookie:
                        logger.info(f"已从 {COOKIE_FILE_PATH} 读取登录凭据")
                        return file_cookie
            except Exception as e:
                logger.warning(f"读取 {COOKIE_FILE_PATH} 失败: {e}")

        # 3. 最后从 config.json 读取 (向下兼容)
        json_cookie = self.raw_config.get("cookie", "").strip()
        if json_cookie:
            logger.info("已从 config.json 读取登录凭据")
            return json_cookie

        return ""

    @staticmethod
    def sanitize_log(text):
        """敏感字段脱敏"""
        if not text:
            return ""
        import re
        text = re.sub(r'(cookie:?\s*[=:]?\s*")[^"]+"', r'\1***MASKED***"', text, flags=re.IGNORECASE)
        text = re.sub(r'(?i)(p_skey|skey|uin|wxuin|luin|qq)=([^;\s]+)', r'\1=***MASKED***', text)
        return text
