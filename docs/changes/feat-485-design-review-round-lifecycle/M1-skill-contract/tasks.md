# feat-485-M1: skill-contract

## Roadpoints

- [x] R1：建立 feat-485 spec/design，并由独立 reviewer 完成首轮 full review。
- [x] R2：逐条处理 R1 findings，复用同一 reviewer 完成下一轮 review。
- [x] 修改 `change-design-author`：unit 级固定 reviewer、事实型 follow-up、author Resolution、最新 Round Gate。
- [x] 修改 `change-design-reviewer`：reviewer-owned mode、retained coverage、时间记录、按 Round 追加。
- [x] 同步 `docs/changes/readme.md` 与 `AGENTS.md`。
- [x] 根据用户反馈撤回 `change-orchestrator` 修改，移除 sha256、byte length 与 manifest 机制，删除文档字符串契约测试。
- [x] 运行两个 skill validator、相邻 contract/frontmatter tests 和 `git diff --check`。

## 退出标准

- [x] `[reviewer]` 固定 reviewer、mode 路由、轮次历史、时间记录与主仓隔离场景均有明确落点。
- [x] `[worker]` 两个 skill validator 通过。
- [x] `[worker]` 相邻 contract/frontmatter tests `9 passed`。
- [x] `[worker]` `git diff --check` 通过。
