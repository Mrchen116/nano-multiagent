# DolphinBench memory-to-action evaluation

本套件将 [DolphinBench](https://github.com/mem0ai/dolphinbench)（锁定提交 `81cb6f8405b40a9e76089cef650806a80af06ea2`）接入 Nano Personal Assistant 的真实接收、原生活动窗口切换、本地凌晨 `03:00` 自动 `Dreaming`、封存只读记忆与模拟 MCP 应用工具链路，并使用 DolphinBench 原生 `grade_tool_trace`（确定性断言 + `field_llm_judge`）评分。

## 特性与隔离边界

- **逐条断点续跑**：每完成一条历史摄入（`ingestion/<persona>/sessions/<id>.json` + `chat-checkpoint.sqlite`）或一道测试题（`tests/<arm>/<persona>/<id>.json`）立即原子落盘；中断后传入同一 `--output` 自动从断点续跑。
- **支持快速切片与全量运行**：
  - `--session-range START:END` 可指定连续历史切片（如 `1:10` 或 `3280:3400`），未传 `--tests` 时自动筛选 `load_bearing_facts` 完全落在该切片内的测试题；
  - 省略 `--session-range` 即运行该人物完整历史（如 Morgan 全量 3,400 条 + 200 题）。
- **支持三路消融与并发测试（`--arms` / `--test-workers`）**：同一份封存快照可连续运行 `product`（记忆文档 + `conversations` 聊天检索）、`search-only`（空记忆文档 + `conversations` 检索）、`memory-only`（仅记忆文档，禁 `conversations` 检索）；封板后的冷上下文测试任务默认 4 并发执行（`--test-workers 4`）。
- **外部磁盘友好**：`--output` 支持任意本地或外置移动硬盘路径（如 NTFS/exFAT 外置盘；若外置盘用于长周期摄取，可配合 `--ingestion-state-dir` 将活跃 SQLite/DSH 符号链接状态放在本机 APFS 目录），单题测试临时沙箱自动落在本机 `/tmp` 并在结束后立即回收。

## 先看计划（零模型调用）

```bash
python3 evals/dolphinbench/run.py \
  --persona morgan \
  --session-range 1:10 \
  --arms product,search-only,memory-only \
  --output /tmp/nano-dolphin-plan \
  --plan-only
```

## 运行小切片验证

```bash
pnpm --filter @nano/dsh-integration... --filter @nano/personal-assistant... --filter @nano/im-server... build
python3 evals/dolphinbench/run.py \
  --persona morgan \
  --session-range 1:10 \
  --arms product,search-only,memory-only \
  --model codexOAuth:gpt-6.2-sol \
  --reasoning-effort high \
  --output /tmp/nano-dolphin-morgan-s10
```
