# StudyBuddy

**收藏过、记过笔记，不等于真正学会。**

StudyBuddy 面向软件工程和 AI 工程学习者，是一个本地优先的学习账本。
它只读扫描 Obsidian Markdown 笔记，为概念候选保留来源，帮助你看清：
哪些内容接触过，哪些还缺少独立验证。

[English](README.md) · [架构](docs/ARCHITECTURE.md) · [路线图](docs/ROADMAP.md)

当前是 **Sprint 1 / Alpha CLI**。无需模型、API Key 或账号，安装依赖后可离线运行。

## 一分钟试用

需要 macOS/Linux、Python 3.12+、支持 FTS5 的 SQLite，以及
[uv](https://docs.astral.sh/uv/getting-started/installation/)。在项目目录运行：

```sh
uv sync --locked
uv run --offline python examples/demo.py
```

首次安装依赖需要联网。Demo 使用项目自带的 3 篇合成笔记和临时数据库，
不会读取你的私人 vault；退出后删除临时数据库。

实际演示结果的关键部分：

```text
Copied AI answer: created=True; repeated key: created=False

6 active concept candidates
6 awaiting independent assessment
0 verified mastered (assessment evaluator is not implemented in Sprint 1)
```

这意味着 6 个候选仍待验证。复制 AI 答案、导入笔记，甚至自行记录一次回忆尝试，
都不会自动变成“已掌握”。本轮尚未实现测评或判分器。

## 已实现

- `doctor --vault PATH`：统计可见 Markdown 文件，不读取正文，不创建数据库。
- `index --vault PATH`：按 SHA-256 增量更新，提取 YAML、标题和 Wikilinks。
- `concepts list`：查看状态为 `seen` 的候选及路径、标题锚点、行号、哈希、时间。
- `concepts list --search "TCP retries"`：使用 SQLite FTS5 搜索活跃候选的标题和路径。
- `events add` / `events list`：显式记录和查询学习事件，重复幂等键不会重复追加。
- `progress`：列出接触过但尚未独立验证的候选。
- 重命名、删除、恢复、失效来源保留，以及同一事务中的本地审计记录。

## 接入自己的笔记

`--db` 是全局参数，放在子命令前。数据库必须位于 vault 之外；每个数据库绑定一个 vault。

```sh
uv run --offline studybuddy --db .local/study.sqlite3 doctor --vault /你的/vault/绝对路径
uv run --offline studybuddy --db .local/study.sqlite3 index --vault /你的/vault/绝对路径
uv run --offline studybuddy --db .local/study.sqlite3 concepts list
uv run --offline studybuddy --db .local/study.sqlite3 progress
```

不传 `--db` 时，默认保存在 `$XDG_DATA_HOME/studybuddy/studybuddy.sqlite3`；
未设置该变量时使用 `~/.local/share/studybuddy/studybuddy.sqlite3`。
所有末级命令均支持 `--json`，事件命令的完整用法见 [English README](README.md#use-your-own-vault)。

## 边界与取舍

| 设计 | 原因与代价 |
| --- | --- |
| SQLite WAL + FTS5 | 单机易运行，学习账本和审计原子提交；暂时串行化写入 |
| 笔记只读，跳过隐藏路径和全部符号链接 | 避免修改笔记或越过授权目录；符号链接组织的笔记暂不支持 |
| 候选和自报事件不等于掌握 | 先保证学习证据可信；本轮 `verified_mastered` 固定为 0 |
| 哈希检测更新 | 即使 mtime 未变化也能检测修改；每次仍需读取全部可见 Markdown |
| 只对唯一的同哈希缺失/新增文件配对重命名 | 尽量保留身份；重命名同时改内容、重复文件有歧义时保守地记为删除+新增 |

数据库会保存 vault 路径、frontmatter、标题、链接、哈希、时间及学习事件，**不保存笔记正文**。
这些元数据仍可能敏感，数据库没有内置加密。运行时没有网络调用、遥测或后台监控。
文件须为 UTF-8，单篇不超过 2 MiB。YAML 错误只报告错误码，不打印正文。
本轮暂不提供测评、MCP、复习调度、词汇、前端或 Windows 支持。

## 开发与开源准备

```sh
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline pytest -q
uv build
```

项目包含 MIT License、中英文文档、贡献指南、Issue/PR 模板、GitHub Actions 和设计决策。
本地验证见 [VALIDATION.md](docs/VALIDATION.md)，CI 尚需推送后在 GitHub 实际运行。
原始蓝图存放在 `docs/vision/`，代表未来规划，不代表当前功能。

后续优先做可追溯测评与证据状态投影，再考虑 MCP 和复习队列。
欢迎用合成笔记提交可复现问题；如果这个方向对你有用，也欢迎在 GitHub 上 Star。
