import argparse
import logging
import sys

from src.classifier import SongClassifier
from src.config import AppConfig
from src.exporter import PlaylistExporter
from src.qqmusic_api import AuthenticationError, QQMusicAPI, QQMusicError
from src.repository import Repository


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def category_names(config):
    """按配置顺序返回全部可导出的分类名。"""
    names = []
    for dimension in ("languages", "genres", "emotions"):
        names.extend(config.categories.get(dimension, {}).keys())
    return list(dict.fromkeys(names))


def classify_songs(config, repo, songs):
    """把 QQ 详情缓存合并到歌曲，并应用本地规则分类。"""
    metadata_cache = repo.load_metadata_cache()
    overrides = repo.load_overrides()
    classifier = SongClassifier(
        config_categories=config.categories,
        overrides=overrides,
        min_confidence=config.min_confidence,
    )

    review_count = 0
    for song in songs:
        detail = metadata_cache.get(str(song.get("mid", "")), {})
        classification_input = dict(song)
        for key in ("language", "genre", "tags"):
            if key in detail:
                classification_input[key] = detail[key]
        song["classification"] = classifier.classify_song(classification_input)
        if song["classification"].get("needs_review"):
            review_count += 1

    repo.save_songs(songs)
    return review_count


def cmd_demo(config, repo):
    logger.info("=== 运行规则自动分类演示模式 (demo) ===")
    mock_songs = [
        {
            "mid": "001",
            "name": "海阔天空",
            "singer": "Beyond",
            "album": "乐与怒",
            "language": "粤语",
            "genre": "摇滚",
            "tags": ["热血"],
        },
        {
            "mid": "002",
            "name": "Example Song",
            "singer": "Example Artist",
            "album": "Demo",
            "language": "英语",
            "genre": "流行",
            "tags": ["治愈"],
        },
        {
            "mid": "003",
            "name": "未知歌曲",
            "singer": "未知歌手",
            "album": "",
            "language": "",
            "genre": "",
            "tags": [],
        },
    ]
    classifier = SongClassifier(config.categories, min_confidence=config.min_confidence)
    for song in mock_songs:
        song["classification"] = classifier.classify_song(song)

    exporter = PlaylistExporter(config.output_dir, categories=category_names(config))
    report_path = exporter.export_all(mock_songs)
    logger.info("[+] 演示完成，综合报告存至: %s", report_path)
    return 0


def cmd_fetch(config, repo):
    logger.info("=== 运行抓取模式 (fetch) ===")
    if not config.cookie:
        logger.error(
            "[ERR] 未配置有效的 Cookie。请设置 QQMUSIC_COOKIE 环境变量，或在 cookie.txt 中写入完整 Cookie。"
        )
        return 2

    api = QQMusicAPI(cookie_str=config.cookie, user_uin=config.user_uin)
    try:
        api.validate_login()
    except AuthenticationError as exc:
        logger.error("[ERR] 登录态无效: %s", exc)
        return 3
    except QQMusicError as exc:
        logger.error("[ERR] 无法验证登录态: %s", exc)
        return 4

    checkpoint = repo.load_checkpoint()
    start_begin = 0 if config.refresh or checkpoint.get("complete") else checkpoint.get("next_begin", 0)

    try:
        songs = api.get_favorite_songs(start_begin=start_begin, repository=repo)
    except AuthenticationError as exc:
        logger.error("[ERR] 抓取过程中登录态失效: %s", exc)
        return 3
    except QQMusicError as exc:
        logger.error("[ERR] 抓取失败，已保留当前检查点: %s", exc)
        return 4

    if not songs and start_begin == 0:
        logger.error("[ERR] 未能拉取到任何歌曲数据")
        return 4
    repo.save_songs(songs)

    cache = repo.load_metadata_cache()
    required_metadata = {"language", "genre", "tags"}
    missing_mids = [
        str(song["mid"])
        for song in songs
        if str(song["mid"]) not in cache
        or not required_metadata.issubset(cache[str(song["mid"])])
    ]

    failed_count = 0
    if missing_mids:
        logger.info("开始抓取 %d 首歌曲的分类元数据...", len(missing_mids))
        pending_cache = {}
        for index, mid in enumerate(missing_mids, 1):
            try:
                detail = api.get_song_detail(mid)
                pending_cache[mid] = detail
                cache[mid] = detail
            except QQMusicError as exc:
                failed_count += 1
                repo.log_failure(mid, reason=str(exc), operation="metadata")
            if len(pending_cache) >= 20:
                repo.save_metadata_items(pending_cache)
                pending_cache.clear()
            if index % 20 == 0:
                logger.info("元数据抓取进度: %d/%d", index, len(missing_mids))
        if pending_cache:
            repo.save_metadata_items(pending_cache)

    logger.info("[+] 数据抓取完成，共 %d 首歌曲，详情失败 %d 首。", len(songs), failed_count)
    return 5 if failed_count else 0


def cmd_retry_failures(config, repo):
    logger.info("=== 重试失败的单曲详情 (retry-failures) ===")
    failures = repo.load_failures()
    if not failures:
        logger.info("没有待重试项目。")
        return 0
    if not config.cookie:
        logger.error("[ERR] 未配置有效的 Cookie，无法重试。")
        return 2

    api = QQMusicAPI(cookie_str=config.cookie, user_uin=config.user_uin)
    remaining = []
    recovered = {}
    for item in failures:
        mid = item.get("mid")
        if not mid or item.get("operation", "metadata") != "metadata":
            remaining.append(item)
            continue
        try:
            recovered[mid] = api.get_song_detail(mid)
        except QQMusicError as exc:
            remaining.append({**item, "reason": str(exc)})

    if recovered:
        repo.save_metadata_items(recovered)
    repo.replace_failures(remaining)
    logger.info("重试完成：恢复 %d 首，仍失败 %d 首。", len(recovered), len(remaining))
    return 5 if remaining else 0


def cmd_classify(config, repo):
    logger.info("=== 运行规则自动分类模式 (classify) ===")
    songs = repo.load_songs()
    if not songs:
        logger.error("[ERR] 本地没有歌曲数据，请先执行 `python main.py fetch`")
        return 4

    review_count = classify_songs(config, repo, songs)
    logger.info(
        "[+] 规则分类完成：%d 首已处理，%d 首因信息不足或置信度较低进入复核清单。",
        len(songs),
        review_count,
    )
    return 0


def cmd_export(config, repo):
    logger.info("=== 运行数据导出模式 (export) ===")
    songs = repo.load_songs()
    if not songs:
        logger.error("[ERR] 未找到可导出的数据，请先执行 `python main.py classify`")
        return 4

    exporter = PlaylistExporter(config.output_dir, categories=category_names(config))
    report_path = exporter.export_all(songs)
    logger.info("[+] 导出成功，报告文件路径: %s", report_path)
    return 0


def cmd_run(config, repo):
    logger.info("=== 运行全流程流水线 (run) ===")
    fetch_result = cmd_fetch(config, repo)
    partial = fetch_result == 5
    if fetch_result not in (0, 5):
        return fetch_result

    classify_result = cmd_classify(config, repo)
    if classify_result != 0:
        return classify_result
    export_result = cmd_export(config, repo)
    return 5 if partial and export_result == 0 else export_result


def main():
    parser = argparse.ArgumentParser(description="QQ 音乐‘我喜欢’歌单规则自动分类工具")
    parser.add_argument(
        "mode",
        nargs="?",
        default="run",
        choices=["demo", "fetch", "classify", "export", "run", "retry-failures"],
        help="运行模式（默认: run）",
    )
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--output-dir", help="覆盖配置中的输出目录")
    parser.add_argument("--data-dir", help="覆盖配置中的本地数据目录")
    parser.add_argument("--min-confidence", type=float, help="待复核阈值，范围 0 到 1")
    parser.add_argument("--refresh", action="store_true", help="忽略未完成检查点，从第一页完整刷新")
    args = parser.parse_args()

    config = AppConfig(config_path=args.config)
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.data_dir:
        config.data_dir = args.data_dir
    if args.min_confidence is not None:
        if not 0 <= args.min_confidence <= 1:
            parser.error("--min-confidence 必须在 0 到 1 之间")
        config.min_confidence = args.min_confidence
    config.refresh = args.refresh

    repo = Repository(data_dir=config.data_dir)
    mode_map = {
        "demo": cmd_demo,
        "fetch": cmd_fetch,
        "classify": cmd_classify,
        "export": cmd_export,
        "run": cmd_run,
        "retry-failures": cmd_retry_failures,
    }
    sys.exit(mode_map[args.mode](config, repo))


if __name__ == "__main__":
    main()
