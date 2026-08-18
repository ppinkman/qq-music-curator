import hashlib
import json
import logging
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


AI_CATEGORIES = [
    "华语女声",
    "华语男声",
    "华语乐队与组合",
    "欧美女声",
    "千禧华语",
    "千禧欧美",
    "90 年代华语",
    "Y2K 氛围",
    "抒情摇滚",
    "爵士嘻哈",
    "都市 R&B",
    "独立流行",
    "独立摇滚",
    "City Pop",
    "梦幻迷幻",
    "深夜情绪",
]

CategoryName = Literal[
    "华语女声",
    "华语男声",
    "华语乐队与组合",
    "欧美女声",
    "千禧华语",
    "千禧欧美",
    "90 年代华语",
    "Y2K 氛围",
    "抒情摇滚",
    "爵士嘻哈",
    "都市 R&B",
    "独立流行",
    "独立摇滚",
    "City Pop",
    "梦幻迷幻",
    "深夜情绪",
]


class AIClassificationError(RuntimeError):
    pass


class CategoryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: CategoryName
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=80)


class SongDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mid: str
    categories: list[CategoryDecision]
    uncertain: bool
    uncertainty_reason: str = Field(max_length=120)


class BatchDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    songs: list[SongDecision]


SYSTEM_PROMPT = """你是资深音乐策展人。根据你掌握的音乐常识，以及输入中的歌名、歌手、专辑和发行日期，为每首歌从固定的 16 个歌单中做多标签分类。

严禁使用或推断任何未提供的 QQ 音乐标签。允许根据对歌手、歌曲、专辑、发行年代和音乐作品的知识判断。一首歌可命中多个分类；只返回真正符合的分类，宁缺毋滥。若作品、版本或艺人不熟悉，设置 uncertain=true，不要根据中文/英文字符机械猜测。

分类定义：
- 华语女声：华语地区女性独唱；女子组合也可归入。若是明确的乐队/团体，可同时归入“华语乐队与组合”。
- 华语男声：华语地区男性独唱；男子组合也可归入。若是明确的乐队/团体，可同时归入“华语乐队与组合”。
- 华语乐队与组合：华语乐队、双人/多人演唱组合、偶像团体；普通的临时合唱不算固定组合。
- 欧美女声：欧美地区女性独唱或女子组合；重点是艺人身份和音乐市场，不仅看英语歌名。
- 千禧华语：华语作品首次发行于 2000-2009 年。新版/现场版按原作具有代表性的年代判断，并在不确定时降低置信度。
- 千禧欧美：欧美作品首次发行于 2000-2009 年。
- 90 年代华语：华语作品首次发行于 1990-1999 年。
- Y2K 氛围：具有 1999-2005 前后千禧审美，如亮面电子、未来复古、早期数码感、Teen Pop、Eurodance、早期网络感；不等于所有 2000 年代歌曲。
- 抒情摇滚：以摇滚编制/动态为骨架，同时旋律性强、情感抒发突出；普通流行情歌不算。
- 爵士嘻哈：Jazz Rap、爵士采样说唱、爵士和声/器乐主导的 Hip-Hop；普通 Lo-fi 不自动算。
- 都市 R&B：成熟都市感的 R&B、Neo-Soul、Smooth R&B，重视律动、夜色和精致制作；普通流行抒情不算。
- 独立流行：Indie Pop、Bedroom Pop 或明显独立审美的流行作品；主流流行歌手不因歌曲冷门就算。
- 独立摇滚：Indie Rock 或明确独立场景中的摇滚作品。
- City Pop：以日本 1970s-1980s 都市流行为核心，也可包含明确延续该编曲美学的现代作品；普通城市感流行不算。
- 梦幻迷幻：Dream Pop、Shoegaze、Psychedelic Pop/Rock、迷幻电子或明显朦胧漂浮的作品。
- 深夜情绪：适合深夜独处、低照度城市、克制忧郁或沉浸聆听的作品；不要把所有慢歌都放入。

置信度基准：0.90 以上为高度确定；0.75-0.89 为可靠；0.55-0.74 为有依据但建议复核；低于 0.55 不要输出该分类。每个 reason 用简短中文说明作品/艺人/年代/风格依据。"""


class OpenAIMusicClassifier:
    VERSION = "ai-v1"

    def __init__(
        self,
        model="gpt-5.4-mini",
        min_confidence=0.7,
        api_key=None,
        client=None,
    ):
        self.model = model
        self.min_confidence = float(min_confidence)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        self._client = client

    @property
    def prompt_version(self):
        digest = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]
        return f"{self.VERSION}:{digest}"

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise AIClassificationError(
                "未设置 OPENAI_API_KEY。请先设置环境变量，再运行 AI 分类。"
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIClassificationError(
                "未安装 openai 依赖，请执行 `python -m pip install -r requirements.txt`。"
            ) from exc
        self._client = OpenAI(api_key=self.api_key)
        return self._client

    @staticmethod
    def _song_input(song):
        # 有意不读取 language / genre / tags，避免 QQ 标签参与 AI 判断。
        return {
            "mid": str(song.get("mid", "")),
            "name": str(song.get("name", "")),
            "singer": str(song.get("singer", "")),
            "album": str(song.get("album", "")),
            "release_date": str(song.get("release_date", "")),
        }

    def classify_batch(self, songs):
        if not songs:
            return {}
        expected = [str(song.get("mid", "")) for song in songs]
        if any(not mid for mid in expected):
            raise AIClassificationError("待分类歌曲缺少 MID")

        payload = json.dumps(
            {"songs": [self._song_input(song) for song in songs]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            response = self._get_client().responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": payload},
                ],
                text_format=BatchDecision,
            )
            parsed = response.output_parsed
        except AIClassificationError:
            raise
        except Exception as exc:
            raise AIClassificationError(f"OpenAI 分类请求失败：{type(exc).__name__}: {exc}") from exc

        if parsed is None:
            raise AIClassificationError("OpenAI 未返回可解析的分类结果")
        if not isinstance(parsed, BatchDecision):
            parsed = BatchDecision.model_validate(parsed)

        by_mid = {decision.mid: decision for decision in parsed.songs}
        if set(by_mid) != set(expected):
            missing = sorted(set(expected) - set(by_mid))
            extra = sorted(set(by_mid) - set(expected))
            raise AIClassificationError(f"AI 返回 MID 不完整：missing={missing}, extra={extra}")

        return {mid: self._normalize(by_mid[mid]) for mid in expected}

    def _normalize(self, decision):
        accepted = [
            item for item in decision.categories if item.confidence >= self.min_confidence
        ]
        all_scores = {item.category: round(item.confidence, 2) for item in decision.categories}
        reasons = {item.category: item.reason.strip() for item in decision.categories}
        accepted_names = [item.category for item in accepted]
        accepted_confidences = [item.confidence for item in accepted]
        overall = round(min(accepted_confidences), 2) if accepted_confidences else 0.0
        needs_review = decision.uncertain or not accepted_names or any(
            score < 0.75 for score in accepted_confidences
        )
        return {
            "categories": accepted_names,
            "confidence": {"overall": overall, "by_category": all_scores},
            "reasons": reasons,
            "evidence": [f"ai:{name}:{reasons.get(name, '')}" for name in accepted_names],
            "needs_review": needs_review,
            "uncertainty_reason": decision.uncertainty_reason.strip(),
            "source": "openai",
            "model": self.model,
            "prompt_version": self.prompt_version,
        }
