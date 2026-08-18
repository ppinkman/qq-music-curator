# QQ 音乐“我喜欢”歌单智能分类工具

这是一个本地优先的 Python 工具：抓取 QQ 音乐“我喜欢”歌曲，再根据歌曲、歌手、专辑、发行年代和音乐常识进行多标签策展，并导出 TXT、CSV、JSON 和复核报告。QQ 音乐自带的语种、曲风和标签不会参与判断。

> QQ 音乐网页接口不是承诺稳定的公开 API。抓取、分类和导出命令不会修改账号；只有显式运行 `import-qq` 才会新建或补全 `AI·` 歌单。

## 快速开始

需要 Python 3.9 或更高版本。

```powershell
python -m pip install -r requirements.txt
python main.py demo
```

演示输出位于 `output/`。真实抓取前，在浏览器登录 QQ 音乐，将请求中的完整 Cookie 保存为当前目录的 `cookie.txt`。该文件已被 `.gitignore` 排除；不要提交或分享它。

没有 OpenAI API Key 时，直接使用当前曲库内由 Codex 整理的本地策展档案：

```powershell
python main.py fetch
python main.py codex-classify
python main.py export
```

也可以直接执行完整流水线；未检测到 `OPENAI_API_KEY` 时会自动使用本地策展，不产生 API 费用：

```powershell
python main.py run
```

分类确认后，可自动创建 16 个 `AI·分类名` 歌单和一个 `AI·待复核` 歌单，并将歌曲写入 QQ 音乐：

```powershell
python main.py import-qq
```

该命令可安全续跑：复用同名歌单，只添加缺失歌曲，不删除已有歌单或其中原有歌曲。每个歌单写入后会重新读取并核验，进度保存在 `data/qq_import_state.json`。

如果另有 [OpenAI API Key](https://platform.openai.com/api-keys)，可以仅在当前 PowerShell 会话中设置后运行模型分类：

```powershell
$env:OPENAI_API_KEY="你的API Key"
python main.py classify --ai-limit 20
python main.py export
```

建议先用 `--ai-limit 20` 检查效果和账户用量。满意后继续运行 `python main.py classify`；已成功分类的歌曲会命中本地缓存，不会重复调用。ChatGPT Plus 订阅本身不包含 OpenAI API 额度。

## 常用命令

```powershell
# 忽略未完成检查点，从第一页重新抓取
python main.py fetch --refresh

# 更改本地数据和输出目录
python main.py demo --data-dir my-data --output-dir my-output

# 将整体置信度低于 0.8 的歌曲放入 review.csv
python main.py classify --min-confidence 0.8

# 不使用 API，重新应用 Codex 本地策展档案
python main.py codex-classify

# 忽略当前 AI 缓存，使用新提示或模型重做（会产生新的 API 用量）
python main.py classify --ai-refresh

# 重试 failures.jsonl 中的单曲详情
python main.py retry-failures

# 运行离线测试
python -m unittest discover -s tests -v
```

Cookie 读取优先级为：`QQMUSIC_COOKIE` 环境变量、`cookie.txt`、`config.json`。不推荐将真实 Cookie 写入 `config.json`。

## 文件说明

- `data/songs.jsonl`：歌曲清单及分类结果。
- `data/metadata_cache.jsonl`：单曲详情缓存，发行日期用于年代判断；QQ 标签不参与 AI 输入。
- `data/ai_classification_cache.jsonl`：保存 OpenAI 或 Codex 本地策展结果。
- `data/checkpoint.json`：分页断点。
- `data/overrides.json`：人工覆盖规则。
- `data/failures.jsonl`：可重试失败项。
- `data/qq_import_state.json`：QQ 音乐自动导入与核验进度。
- `output/playlists/`：分类 TXT。
- `output/songs.csv`、`songs.json`：全量结果。
- `output/review.csv`：未明确命中当前 16 个策展歌单的歌曲。
- `output/summary.md`：汇总报告。

当前固定生成 16 个歌单：华语女声、华语男声、华语乐队与组合、欧美女声、千禧华语、千禧欧美、90 年代华语、Y2K 氛围、抒情摇滚、爵士嘻哈、都市 R&B、独立流行、独立摇滚、City Pop、梦幻迷幻、深夜情绪。

## 安全与免责声明

- 本项目是非官方个人项目，与腾讯或 QQ 音乐没有隶属、授权或背书关系。
- 项目依赖 QQ 音乐未公开承诺稳定的网页接口，接口可能随时变更或失效。请仅在个人学习和管理自己账号数据的范围内使用，并自行遵守适用法律及 QQ 音乐服务协议。
- 请勿提交、分享或记录真实的 `cookie.txt`、QQ 登录令牌、OpenAI API Key 或抓取出的个人数据。如果凭据曾意外公开，请立即在对应平台撤销或刷新。
- 请勿将本项目用于商业服务、大规模抓取、绕过访问控制、版权限制或平台风控。
- [MIT License](LICENSE) 仅授权本仓库源代码，不授予任何音乐、歌词、封面、用户数据、QQ 音乐服务或第三方内容的使用权。

## 许可证

源代码采用 [MIT License](LICENSE) 开源。

人工覆盖示例（保留给后续版本）：

```json
{
  "歌曲MID": {
    "categories": {
      "language": ["粤语"],
      "genre": ["摇滚"],
      "emotion": ["热血"]
    }
  }
}
```

完整设计和后续路线见 `PLAN.md`。
