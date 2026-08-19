# QQ 音乐“我喜欢”自动分类工具

这是一个本地运行的 Python 工具：读取 QQ 音乐“我喜欢”歌单，使用 QQ 音乐返回的语种、曲风和标签，按照 `config.json` 中的规则自动分类，并导出 TXT、CSV、JSON 和复核报告。

本版本不使用 OpenAI、Codex 或其他 AI API，也不会创建、修改或删除 QQ 音乐歌单。所有分类结果只写入本地 `data/` 和 `output/`。

> QQ 音乐网页接口不是承诺稳定的公开 API，可能随时变更或失效。

## 快速开始

需要 Python 3.9 或更高版本。

```powershell
python -m pip install -r requirements.txt
python main.py demo
```

演示输出位于 `output/`，不需要 Cookie，也不会访问 QQ 音乐。

## 分类自己的“我喜欢”

先在浏览器中登录 QQ 音乐，把发往 `y.qq.com` 的请求标头中完整的 `Cookie` 值保存为项目根目录的 `cookie.txt`。只写 Cookie 的值，不要包含 `Cookie:` 这几个字。

然后运行：

```powershell
python main.py run
```

完整流程是：

1. 分页抓取“我喜欢”歌曲并补全语种、曲风、标签。
2. 根据 `config.json` 的本地规则自动分类。
3. 生成各分类 TXT、全量表格和待复核清单。

Cookie 读取优先级为 `QQMUSIC_COOKIE` 环境变量、`cookie.txt`、`config.json`。建议使用前两种方式；`cookie.txt` 已被 `.gitignore` 排除。

## 常用命令

```powershell
# 只抓取和缓存数据
python main.py fetch

# 使用已缓存的 QQ 元数据重新分类
python main.py classify

# 只重新导出结果
python main.py export

# 忽略分页检查点，从第一页完整刷新
python main.py fetch --refresh

# 将整体置信度低于 0.8 的歌曲放入 review.csv
python main.py classify --min-confidence 0.8

# 重试 failures.jsonl 中的单曲详情
python main.py retry-failures

# 运行离线测试
python -m unittest discover -s tests -v
```

如果在线抓取因 QQ 音乐接口变化而失败，可以继续使用已保存在 `data/` 中的数据执行 `classify` 和 `export`。

## 分类规则

默认分类分为三个维度：

- 语种：普通话、粤语、英语、日语、韩语。
- 曲风：流行、摇滚、民谣、电子、R&B、嘻哈、轻音乐。
- 情绪：抒情、热血。

每首歌可以同时进入多个分类。规则位于 `config.json`，支持：

- `include_any`：命中任意关键词即可。
- `include_all`：必须命中全部关键词。
- `exclude`：命中后排除该分类。
- `priority`：控制同维度结果顺序。
- `min_confidence`：该规则的置信度。

例如增加一个“爵士”分类：

```json
"爵士": {
  "include_any": ["爵士", "Jazz", "Bebop", "Swing"],
  "min_confidence": 0.7
}
```

规则依据只来自 QQ 元数据，不会根据歌名或歌手调用 AI 猜测。语种元数据缺失时，仅使用文字字符做保守推断；无法判断的歌曲会进入 `review.csv`。

## 人工覆盖

如果个别歌曲需要修正，可以创建 `data/overrides.json`：

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

重新运行 `python main.py classify` 后，人工覆盖优先于自动规则。

## 文件说明

- `data/songs.jsonl`：歌曲清单及规则分类结果。
- `data/metadata_cache.jsonl`：QQ 音乐语种、曲风和标签缓存。
- `data/checkpoint.json`：分页抓取断点。
- `data/overrides.json`：人工覆盖规则。
- `data/failures.jsonl`：可重试失败项。
- `output/playlists/`：每个分类一个 TXT。
- `output/songs.csv`、`output/songs.json`：全量分类结果。
- `output/review.csv`：信息不足或置信度较低的歌曲。
- `output/summary.md`：分类汇总报告。

## 安全与免责声明

- 本项目是非官方个人项目，与腾讯或 QQ 音乐没有隶属、授权或背书关系。
- 请仅在个人学习和管理自己账号数据的范围内使用，并自行遵守适用法律及 QQ 音乐服务协议。
- 请勿提交或分享真实的 `cookie.txt`、QQ 登录令牌或抓取出的个人数据。若凭据曾意外公开，请立即刷新登录态。
- 请勿将本项目用于商业服务、大规模抓取、绕过访问控制、版权限制或平台风控。
- [MIT License](LICENSE) 只授权本仓库源代码，不授予任何音乐、歌词、封面、用户数据、QQ 音乐服务或第三方内容的使用权。

完整设计见 [PLAN.md](PLAN.md)。
