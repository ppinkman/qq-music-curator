import os
import sys
import argparse
import logging

from src.config import AppConfig
from src.repository import Repository
from src.qqmusic_api import AuthenticationError, QQMusicAPI, QQMusicError
from src.classifier import SongClassifier
from src.ai_classifier import AIClassificationError, AI_CATEGORIES, OpenAIMusicClassifier
from src.codex_curator import CodexMusicCurator
from src.exporter import PlaylistExporter
from src.qqmusic_importer import QQMusicPlaylistImporter, build_playlist_targets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def cmd_demo(config, repo):
    logger.info("=== 运行 AI 分类导出演示模式 (不调用 OpenAI) ===")
    mock_songs = [
        {"mid": "001", "name": "海阔天空", "singer": "Beyond", "album": "乐与怒", "demo_categories": ["华语乐队与组合", "90 年代华语", "抒情摇滚"]},
        {"mid": "002", "name": "晴天", "singer": "周杰伦", "album": "叶惠美", "demo_categories": ["华语男声", "千禧华语", "深夜情绪"]},
        {"mid": "003", "name": "Plastic Love", "singer": "竹内まりや", "album": "VARIETY", "demo_categories": ["City Pop", "深夜情绪"]},
        {"mid": "004", "name": "测试未定名歌曲", "singer": "无名氏", "album": "", "demo_categories": []},
    ]
    for song in mock_songs:
        categories = song.pop("demo_categories")
        song["classification"] = {
            "categories": categories,
            "confidence": {"overall": 0.9 if categories else 0.0, "by_category": {name: 0.9 for name in categories}},
            "reasons": {name: "演示用 AI 策展结果" for name in categories},
            "evidence": [f"ai:{name}:演示用 AI 策展结果" for name in categories],
            "needs_review": not categories,
            "uncertainty_reason": "不认识该作品" if not categories else "",
            "source": "demo_ai",
        }

    exporter = PlaylistExporter(config.output_dir, categories=AI_CATEGORIES)
    report_path = exporter.export_all(mock_songs)
    
    logger.info(f"[+] 演示模式运行成功！综合报告存至: {report_path}")
    return 0

def cmd_fetch(config, repo):
    logger.info("=== 运行抓取模式 (fetch) ===")
    if not config.cookie:
        logger.error("[ERR] 未配置有效的 Cookie，无法在线抓取。设置 QQMUSIC_COOKIE 环境变量或在 cookie.txt 中写入。")
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

    cp = repo.load_checkpoint()
    start_begin = 0 if config.refresh or cp.get("complete") else cp.get("next_begin", 0)
    
    try:
        songs = api.get_favorite_songs(start_begin=start_begin, repository=repo)
    except AuthenticationError as exc:
        logger.error("[ERR] 抓取过程中登录态失效: %s", exc)
        return 3
    except QQMusicError as exc:
        logger.error("[ERR] 抓取失败，已保留当前检查点: %s", exc)
        return 4
    if not songs and start_begin == 0:
        logger.error("[ERR] 未能成功拉取到任何歌曲数据")
        return 4

    repo.save_songs(songs)
    
    # 补全单曲详情缓存
    cache = repo.load_metadata_cache()
    # 老缓存可能只有 QQ 标签而没有发行日期；AI 年代分类需要补抓客观发行时间。
    missing_mids = [
        song["mid"]
        for song in songs
        if song["mid"] not in cache or "release_date" not in cache[song["mid"]]
    ]
    
    failed_count = 0
    if missing_mids:
        logger.info(f"开始抓取 {len(missing_mids)} 首新增歌曲的详细元数据...")
        pending_cache = {}
        for idx, mid in enumerate(missing_mids, 1):
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
            if idx % 20 == 0:
                logger.info(f"元数据抓取进度: {idx}/{len(missing_mids)}")
        if pending_cache:
            repo.save_metadata_items(pending_cache)

    logger.info("[+] 数据抓取完成，共计 %d 首歌曲，详情失败 %d 首。", len(songs), failed_count)
    return 5 if failed_count else 0


def cmd_retry_failures(config, repo):
    logger.info("=== 重试失败的单曲详情 ===")
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
    logger.info("=== 运行 OpenAI 智能分类模式 (classify) ===")
    songs = repo.load_songs()
    if not songs:
        logger.error("[ERR] 本地未找到已抓取的歌曲数据，请先执行 `python main.py fetch`")
        return 4

    metadata_cache = repo.load_metadata_cache()
    for song in songs:
        detail = metadata_cache.get(song["mid"], {})
        # 只引入客观发行日期；QQ 的 language/genre/tags 不参与 AI 输入。
        if detail.get("release_date"):
            song["release_date"] = detail["release_date"]

    classifier = OpenAIMusicClassifier(
        model=config.ai_model,
        min_confidence=config.min_confidence,
    )
    ai_cache = repo.load_ai_cache(
        model=classifier.model,
        prompt_version=classifier.prompt_version,
    )
    if config.ai_refresh:
        repo.clear_ai_cache(
            model=classifier.model,
            prompt_version=classifier.prompt_version,
        )
        ai_cache = {}

    pending = [song for song in songs if song["mid"] not in ai_cache]
    if config.ai_limit is not None:
        pending = pending[: config.ai_limit]

    logger.info(
        "AI 模型=%s，缓存命中=%d，待分类=%d，总歌曲=%d",
        classifier.model,
        len(songs) - len([song for song in songs if song["mid"] not in ai_cache]),
        len(pending),
        len(songs),
    )

    if pending and not classifier.api_key:
        logger.error(
            "[ERR] 未设置 OPENAI_API_KEY。请先在当前 PowerShell 设置环境变量；不会自动发起付费请求。"
        )
        return 2

    failed = False
    for start in range(0, len(pending), config.ai_batch_size):
        batch = pending[start : start + config.ai_batch_size]
        try:
            results = classifier.classify_batch(batch)
        except AIClassificationError as exc:
            logger.error("[ERR] AI 分类在第 %d 批失败，已保存此前进度: %s", start // config.ai_batch_size + 1, exc)
            failed = True
            break
        repo.save_ai_items(results)
        ai_cache.update({mid: {**result, "mid": mid} for mid, result in results.items()})
        logger.info("AI 分类进度: %d/%d", min(start + len(batch), len(pending)), len(pending))

    classified_count = 0
    for song in songs:
        cached = ai_cache.get(song["mid"])
        if cached:
            song["classification"] = {key: value for key, value in cached.items() if key != "mid"}
            classified_count += 1
        else:
            song.pop("classification", None)
    repo.save_songs(songs)
    logger.info("[+] AI 分类结果已写入 %d/%d 首歌曲。", classified_count, len(songs))
    return 5 if failed or classified_count < len(songs) else 0


def cmd_codex_classify(config, repo):
    """使用当前项目内由 Codex 策展的本地档案分类，不调用任何付费 API。"""
    logger.info("=== 运行 Codex 本地策展分类模式 (codex-classify) ===")
    songs = repo.load_songs()
    if not songs:
        logger.error("[ERR] 本地未找到已抓取的歌曲数据，请先执行 `python main.py fetch`")
        return 4

    curator = CodexMusicCurator()
    metadata_cache = repo.load_metadata_cache()
    results = curator.classify_all(songs, metadata_cache)
    repo.save_ai_items(results)

    for song in songs:
        result = results.get(str(song.get("mid", "")))
        if result:
            song["classification"] = result
    repo.save_songs(songs)

    review_count = sum(bool(item.get("needs_review")) for item in results.values())
    logger.info(
        "[+] Codex 本地策展完成：%d/%d 首已写入，%d 首进入复核清单；未调用 OpenAI API。",
        len(results),
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

    exporter = PlaylistExporter(config.output_dir, categories=AI_CATEGORIES)
    report_path = exporter.export_all(songs)
    logger.info(f"[+] 导出成功！报告文件路径: {report_path}")
    return 0


def cmd_import_qq(config, repo):
    logger.info("=== 自动导入 QQ 音乐歌单 (import-qq) ===")
    songs = repo.load_songs()
    if not songs:
        logger.error("[ERR] 本地没有歌曲数据，请先运行 `python main.py run`")
        return 4
    if not config.cookie:
        logger.error("[ERR] 未配置 QQ 音乐 Cookie")
        return 2

    api = QQMusicAPI(cookie_str=config.cookie, user_uin=config.user_uin)
    try:
        api.validate_login()
        targets = build_playlist_targets(songs)
        importer = QQMusicPlaylistImporter(
            api,
            repo,
            songs=songs,
            batch_size=config.import_batch_size,
        )
        report = importer.import_targets(targets)
    except AuthenticationError as exc:
        logger.error("[ERR] QQ 音乐登录态无效：%s", exc)
        return 3
    except QQMusicError as exc:
        logger.error("[ERR] 自动导入中止，进度已保存：%s", exc)
        return 4

    missing = sum(item["missing_count"] for item in report.values())
    verified = sum(item["verified_count"] for item in report.values())
    logger.info(
        "[+] QQ 音乐导入核验完成：17 个歌单，共 %d 条分类归属已写入，缺少 %d 条",
        verified,
        missing,
    )
    return 5 if missing else 0

def cmd_run(config, repo):
    logger.info("=== 运行全流程流水线 (run) ===")
    ret = cmd_fetch(config, repo)
    partial = ret == 5
    if ret not in (0, 5):
        return ret
    if os.getenv("OPENAI_API_KEY", "").strip():
        ret = cmd_classify(config, repo)
    else:
        logger.info("未检测到 OPENAI_API_KEY，自动使用 Codex 本地策展结果，不产生 API 费用。")
        ret = cmd_codex_classify(config, repo)
    if ret != 0:
        return ret
    ret = cmd_export(config, repo)
    return 5 if partial and ret == 0 else ret

def main():
    parser = argparse.ArgumentParser(description="QQ音乐“我喜欢”歌单智能分类工具 v2.0")
    parser.add_argument("mode", nargs="?", default="run", 
                        choices=["demo", "fetch", "classify", "codex-classify", "export", "import-qq", "run", "retry-failures"],
                        help="运行模式 (默认: run)")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--output-dir", help="覆盖配置中的输出目录")
    parser.add_argument("--data-dir", help="覆盖配置中的本地数据目录")
    parser.add_argument("--min-confidence", type=float, help="待复核阈值，范围 0 到 1")
    parser.add_argument("--refresh", action="store_true", help="忽略未完成检查点，从第一页完整刷新")
    parser.add_argument("--ai-model", help="OpenAI 分类模型，默认读取 config.json")
    parser.add_argument("--ai-batch-size", type=int, help="每次发送给 AI 的歌曲数，默认 20")
    parser.add_argument("--ai-limit", type=int, help="本次最多新分类多少首，用于小批量试运行")
    parser.add_argument("--ai-refresh", action="store_true", help="忽略当前模型的 AI 缓存并重新分类")
    parser.add_argument("--import-batch-size", type=int, default=50, help="QQ 歌单单批添加数量，1 到 50")

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
    config.ai_refresh = args.ai_refresh
    config.ai_limit = args.ai_limit
    if args.ai_model:
        config.ai_model = args.ai_model
    if args.ai_batch_size is not None:
        if args.ai_batch_size <= 0:
            parser.error("--ai-batch-size 必须大于 0")
        config.ai_batch_size = args.ai_batch_size
    if args.ai_limit is not None and args.ai_limit <= 0:
        parser.error("--ai-limit 必须大于 0")
    if not 1 <= args.import_batch_size <= 50:
        parser.error("--import-batch-size 必须在 1 到 50 之间")
    config.import_batch_size = args.import_batch_size
    repo = Repository(data_dir=config.data_dir)

    mode_map = {
        "demo": cmd_demo,
        "fetch": cmd_fetch,
        "classify": cmd_classify,
        "codex-classify": cmd_codex_classify,
        "export": cmd_export,
        "import-qq": cmd_import_qq,
        "run": cmd_run,
        "retry-failures": cmd_retry_failures,
    }

    handler = mode_map[args.mode]
    exit_code = handler(config, repo)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
