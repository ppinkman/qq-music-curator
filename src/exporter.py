import os
import csv
import json
import logging

logger = logging.getLogger(__name__)

class PlaylistExporter:
    def __init__(self, output_dir="output", categories=None):
        self.output_dir = output_dir
        self.categories = list(categories or [])
        self.playlists_dir = os.path.join(self.output_dir, "playlists")
        os.makedirs(self.playlists_dir, exist_ok=True)

    def export_all(self, songs_classified):
        """
        导出所有产品目标文件：TXT歌单、CSV全量表、JSON数据、review复核表、Markdown报告。
        """
        # 1. 拆分歌单字典
        categorized_map = {name: [] for name in self.categories}
        review_songs = []

        for song in songs_classified:
            classification = song.get("classification")
            if not classification:
                review_songs.append(song)
                continue
            cats = classification.get("categories", [])
            needs_review = classification.get("needs_review", False)
            
            if needs_review:
                review_songs.append(song)

            # AI 新格式直接返回固定歌单名；兼容旧格式仅用于 demo。
            if isinstance(cats, dict):
                all_cat_names = [name for names in cats.values() for name in names]
            else:
                all_cat_names = list(cats)
            for cat_name in dict.fromkeys(all_cat_names):
                if self.categories and cat_name not in self.categories:
                    continue
                if cat_name not in categorized_map:
                    categorized_map[cat_name] = []
                categorized_map[cat_name].append(song)

        # 2. 导出 TXT 歌单
        self._export_txt_playlists(categorized_map)

        # 3. 导出 CSV 全量表格
        self._export_songs_csv(songs_classified)

        # 4. 导出 JSON 全量文件
        self._export_songs_json(songs_classified)

        # 5. 导出 review.csv 待复核清单
        self._export_review_csv(review_songs)

        # 6. 导出 summary.md 汇总报告
        summary_path = self._export_summary_md(songs_classified, categorized_map, review_songs)

        return summary_path

    def _export_txt_playlists(self, categorized_map):
        expected_files = {f"{name}.txt" for name in categorized_map}
        for filename in os.listdir(self.playlists_dir):
            filepath = os.path.join(self.playlists_dir, filename)
            if filename.endswith(".txt") and filename not in expected_files and os.path.isfile(filepath):
                os.remove(filepath)
        for cat_name, songs in categorized_map.items():
            filepath = os.path.join(self.playlists_dir, f"{cat_name}.txt")
            temp_path = filepath + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                for song in songs:
                    f.write(f"{song['name']} - {song['singer']}\n")
            os.replace(temp_path, filepath)
            logger.info(f"已生成歌单 TXT: {filepath} ({len(songs)} 首)")

    def _export_songs_csv(self, songs):
        filepath = os.path.join(self.output_dir, "songs.csv")
        temp_path = filepath + ".tmp"
        headers = ["mid", "歌名", "歌手", "专辑", "分类结果", "整体置信度", "识别证据", "需复核"]
        
        with open(temp_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for song in songs:
                clf = song.get("classification", {})
                cats_str = json.dumps(clf.get("categories", []), ensure_ascii=False)
                conf = clf.get("confidence", {}).get("overall", 0.0)
                evidence = "|".join(clf.get("evidence", []))
                review = "是" if clf.get("needs_review") else "否"
                writer.writerow([
                    song.get("mid"),
                    song.get("name"),
                    song.get("singer"),
                    song.get("album"),
                    cats_str,
                    conf,
                    evidence,
                    review
                ])
        os.replace(temp_path, filepath)
        logger.info(f"已导出 CSV 全量表格: {filepath}")

    def _export_songs_json(self, songs):
        filepath = os.path.join(self.output_dir, "songs.json")
        temp_path = filepath + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, filepath)
        logger.info(f"已导出机器可读 JSON 数据: {filepath}")

    def _export_review_csv(self, review_songs):
        filepath = os.path.join(self.output_dir, "review.csv")
        temp_path = filepath + ".tmp"
        headers = ["mid", "歌名", "歌手", "分类结果", "整体置信度", "识别证据", "复核原因"]
        
        with open(temp_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for song in review_songs:
                clf = song.get("classification", {})
                cats_str = json.dumps(clf.get("categories", []), ensure_ascii=False)
                conf = clf.get("confidence", {}).get("overall", 0.0)
                evidence = "|".join(clf.get("evidence", []))
                if not clf:
                    reason = "尚未进行 AI 分类"
                else:
                    reason = clf.get("uncertainty_reason") or "AI 置信度偏低或未命中固定分类"
                writer.writerow([
                    song.get("mid"),
                    song.get("name"),
                    song.get("singer"),
                    cats_str,
                    conf,
                    evidence,
                    reason
                ])
        os.replace(temp_path, filepath)
        logger.info(f"已导出待复核清单: {filepath} ({len(review_songs)} 首)")

    def _export_summary_md(self, all_songs, categorized_map, review_songs):
        filepath = os.path.join(self.output_dir, "summary.md")
        temp_path = filepath + ".tmp"
        
        total_count = len(all_songs)
        review_count = len(review_songs)
        coverage_rate = round(((total_count - review_count) / total_count * 100), 1) if total_count > 0 else 0.0

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write("# QQ 音乐“我喜欢”歌单智能分类报告\n\n")
            f.write(f"- **歌曲总数**: {total_count} 首\n")
            classified_count = sum(1 for song in all_songs if song.get("classification"))
            f.write(f"- **已完成 AI 分类**: {classified_count} 首\n")
            f.write(f"- **无需复核**: {total_count - review_count} 首\n")
            f.write(f"- **待复核/低置信度**: {review_count} 首 (`review.csv`)\n")
            f.write(f"- **无需复核比例**: {coverage_rate}%\n\n")
            
            f.write("## 歌单分布明细\n\n")
            f.write("| 歌单分类 | 歌曲数量 | 相对比例 |\n")
            f.write("| --- | --- | --- |\n")
            for cat_name, songs in sorted(categorized_map.items(), key=lambda x: len(x[1]), reverse=True):
                ratio = round(len(songs) / total_count * 100, 1) if total_count > 0 else 0
                f.write(f"| **{cat_name}** | {len(songs)} 首 | {ratio}% |\n")

            f.write("\n## 导出的文档列表\n\n")
            f.write(f"- 📁 TXT 导入歌单: `output/playlists/`\n")
            f.write(f"- 📊 全量明细表格: `output/songs.csv`\n")
            f.write(f"- 🔍 待复核清单: `output/review.csv`\n")
            f.write(f"- 💾 完整 JSON 数据: `output/songs.json`\n")
            
        os.replace(temp_path, filepath)
        logger.info(f"已导出 Markdown 汇总报告: {filepath}")
        return filepath
