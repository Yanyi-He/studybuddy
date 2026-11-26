# StudyBuddy

**收藏过、记过笔记，不等于真正学会。**

StudyBuddy 面向软件工程与 AI 工程学习者：只读接入 Obsidian，保留概念来源，
把接触记录、固定题测评结果与学习状态分开保存，避免把导入或复制答案当作掌握。

**v0.2.0 / Sprint 2 · Alpha CLI · 本地优先 · 无模型依赖 · MIT**

[English](README.md) · [架构](docs/ARCHITECTURE.md) · [路线图](docs/ROADMAP.md) ·
[更新记录](CHANGELOG.md)

## 运行完整演示

需要 macOS/Linux、Python 3.12+、支持 FTS5 的 SQLite 和
[uv](https://docs.astral.sh/uv/getting-started/installation/)。在项目目录运行：

```sh
uv sync --locked
uv run --offline python examples/demo.py
```

首次安装依赖需要联网，运行时完全离线。Demo 使用 3 篇合成笔记、合成答案和临时数据库，
不会读取私人 vault，退出时删除临时数据。实际演示的关键结果：

```text
Synthetic fixed-item answer: score=1.0; state=assessed_once (no delayed retest)
Append-only correction: invalidate -> exposed
Append-only correction: restore -> assessed_once
JSONL round trip: projections and event history preserved
```

演示没有假装等待 24 小时，也不代表真实学习者通过了延迟回忆。

## 当前功能

| 模块 | 命令与行为 |
| --- | --- |
| 笔记索引 | `doctor` / `index`，只读提取 YAML、标题、Wikilinks、SHA-256 与版本 |
| 来源候选 | `concepts list`，保留路径、标题锚点、行号、哈希与时间，支持 FTS5 |
| 自报事件 | `events add/list`，显式记录、幂等追加，不影响测评状态 |
| 版本化测评 | `quiz list/show/start/submit`，9 道原创题，覆盖重试安全、事务隔离、二分查找 |
| 更正与历史 | `quiz correct/history`，追加失效/恢复记录，不覆盖原答案或分数 |
| 状态重放 | `progress --as-of TIME`，支持延迟复测、失败回退和更正后的重新计算 |
| 数据归属 | `export` / `import`，JSONL 校验导出，完整验证后恢复到新数据库 |
| 数据库升级 | `migrate --backup PATH`，v1 升级到 v2 前先生成完整备份 |

所有末级命令支持 `--json`。`--db` 是全局参数，放在子命令前。
本轮不包含 MCP、复习调度、前端、LLM 判分或学习者代码执行。

## 旧数据升级与自己的笔记

新数据库直接使用 v2。Sprint 1 的 v1 数据库需要显式升级，不会在查询时静默迁移：

```sh
uv run --offline studybuddy --db .local/study.sqlite3 migrate \
  --backup .local/study-before-v2.sqlite3
```

备份通过完整性检查后，才原子提交新表、版本与审计；不会覆盖已有备份。
数据库必须位于 vault 外。每个数据库绑定一个规范化的 vault 根目录。

```sh
uv run --offline studybuddy --db .local/study.sqlite3 doctor --vault /你的/vault/绝对路径
uv run --offline studybuddy --db .local/study.sqlite3 index --vault /你的/vault/绝对路径
uv run --offline studybuddy --db .local/study.sqlite3 concepts list
uv run --offline studybuddy --db .local/study.sqlite3 progress
```

不传 `--db` 时，使用 `$XDG_DATA_HOME/studybuddy/studybuddy.sqlite3`，
未设置时回退到 `~/.local/share/studybuddy/studybuddy.sqlite3`。

## 做一次测评

先运行 `quiz list` / `quiz show retry-recall` 看题目。选择相关概念，将其完整 `c_...`
ID 放入 `STUDYBUDDY_CONCEPT_ID`。固定题并非从私人笔记自动生成，首次选题会把该概念
显式绑定到一个题目主题，禁止混用无关主题的成绩。

```sh
uv run --offline studybuddy --db .local/study.sqlite3 quiz start \
  --concept "$STUDYBUDDY_CONCEPT_ID" --assessment retry-recall \
  --idempotency-key retry-session-001 --json
```

保存返回的 `s_...` 为 `STUDYBUDDY_SESSION_ID`，按题目选择项填写自己的 JSON 答案文件：

```sh
uv run --offline studybuddy --db .local/study.sqlite3 quiz submit \
  --session "$STUDYBUDDY_SESSION_ID" --answer-file .local/my-answer.json \
  --assistance independent --hints-used 0 --idempotency-key retry-answer-001
```

辅助情况必须声明为 `independent`、`assisted` 或 `ai_generated`；独立作答不能同时报告提示。
每个 session 只收一次答案，重试同一幂等键返回原记录，换答案复用键会报冲突。
分数来自确定性选项校验，不接受调用方提供分数、判分器版本或“已掌握”标志。
可附 `explanation`，但它只保存、不判分。

如果后来发现用了帮助或记录归属有误，用返回的 `a_...` 追加更正：

```sh
uv run --offline studybuddy --db .local/study.sqlite3 quiz correct \
  --attempt "$STUDYBUDDY_ATTEMPT_ID" --action invalidate \
  --reason "该次作答借助了外部帮助" --idempotency-key correction-001
```

`restore` 可以恢复已失效结果，须另给原因和幂等键。原始答案、分数和更正均保留。

## 状态如何变化

候选仍为 `status=seen`；测评产生独立的 `learning_state`，附支持结果 ID 与投影版本。

| 状态 | 当前规则 |
| --- | --- |
| `exposed` | 只有笔记/自报事件，没有有效测评结果 |
| `answered_with_help` | 在辅助或 AI 帮助下通过固定题 |
| `assessed_once` | 声明独立且通过一次，尚无延迟复测证据 |
| `recalled_unassisted` | 两次独立回忆成功；第二题发放距第一次提交至少 24 小时 |
| `applied` | 已有延迟回忆证据，再通过后续应用场景题 |
| `transferred` | 之后在不同上下文通过迁移场景题 |
| `needs_review` | 任一有效失败清空当前证据链，需要重新验证 |

当天刷题、提前开题后一直放着，都不满足延迟门槛。辅助成功不提升独立状态。
撤销成功可能降低状态，撤销错误记录的失败可能恢复早先证据；一切从历史重新推导。
`--as-of` 重放指定时间前已知的结果/更正，来源列表仍是当前活跃笔记。

**这些是固定题范围内的产品启发式，不是科学掌握标准。** 是否有外部帮助仍由学习者声明，
本机时钟没有外部认证，开源题库也含答案。自由文本推理、生产编程能力和整体掌握不被认证；
`verified_mastered` 保持为 0。导入笔记或复制 AI 答案不会提升学习状态。

## 导出与恢复

```sh
uv run --offline studybuddy --db .local/study.sqlite3 export --output .local/study.ledger.jsonl
uv run --offline studybuddy --db .local/restored.sqlite3 import \
  --input .local/study.ledger.jsonl --vault /你的/vault/绝对路径
```

只恢复到不存在的新数据库，不合并、不覆盖。用户显式选择 vault，文件里的根路径不构成授权。
格式包含来源上下文、自报事件、题目版本、答案和更正，末尾带数量与 SHA-256 校验；上限 64 MiB。
恢复前会校验结构、关联、路径、时间、题目版本并重新判分，截断文件、伪造分数或篡改题库会被拒绝。
校验和不是签名，也不能证明学习行为真实。

导出包含私人元数据和答案，不加密；不含操作审计或可重建的 FTS 缓存。
完整数据库/审计备份使用 SQLite backup API，详见 [架构](docs/ARCHITECTURE.md)。

## 验证与开发

```sh
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline pytest -q
uv build
uv run --offline python scripts/smoke_wheel.py
```

包含 32 条合成学习历史、旧数据迁移/回滚、幂等与并发、来源删除、恶意导入和往返测试。
实际本地结果见 [VALIDATION.md](docs/VALIDATION.md)。GitHub CI 已配置，仍需推送后验证。
源码目录外的 wheel 安装演示也验证了题库与 SQL 迁移资源的打包。

笔记只读、跳过隐藏路径和全部符号链接，UTF-8 单篇上限 2 MiB。数据库不保存笔记正文，
但 frontmatter、标题、链接、事件和答案仍可能敏感；无遥测、运行时网络请求或内置加密。
Windows、大型 vault 性能及多用户托管不在本轮范围。

欢迎用合成笔记报告问题、补充回归历史。原始蓝图位于 `docs/vision/`，代表长期规划，
不是已实现功能；若这个方向对你有用，也欢迎在 GitHub 上 Star。
