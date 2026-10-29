# Codex Memory V2 原始参考快照

来源：openai/codex，commit `8fdf6472955749a731fd9e4b8ffc218e8e80c51d`，2026-10-29 本地 fetch 后核对。三个模板与 LICENSE/NOTICE 按原字节复制，不翻译、不删改。许可证及 NOTICE 原样保留；本目录是研究输入，不是 Nano 运行时资产或指令。

- [单会话提炼系统提示](stage_one_system_v2.md)
- [单会话提炼输入模板](stage_one_input_v2.md)
- [跨会话整理模板](consolidation_v2.md)
- [LICENSE](LICENSE)、[NOTICE](NOTICE)

| 原件 | SHA-256 |
| --- | --- |
| `stage_one_system_v2.md` | `334c0d51a2c63bd317dac074155fb3ecf0a56af8b00657736bab9c74222372b4` |
| `stage_one_input_v2.md` | `8fd4bb25fe6bd746b2d46ad841ac3a195d220c3da0cb9230615e2347c6ef853e` |
| `consolidation_v2.md` | `7334fdb4aa5d958bcff54568a375d0b0145c19a611a1a22faa6bf251a46a5f0e` |
| `LICENSE` | `d17f227e4df5da1600391338865ce0f3055211760a36688f816941d58232d8dc` |
| `NOTICE` | `9d71575ecfd9a843fc1677b0efb08053c6ba9fd686a0de1a6f5382fd3c220915` |

## 实施阅读入口

不能只读这三份模板就宣称复用完成。实施者必须按相同 commit 读取以下源码及相邻测试，记录采用的机制与必要差异；原始仓库本机位置由 dev-host reference_root 定位，不写死成产品依赖。

- `codex-rs/memories/write/src/rollout_input.rs`：sanitization、来源分层、真人问答配对、优先级、近期选择、裁剪标记、媒体占位、最终时序和 extraction_messages；注意消息分块仍是一次请求。
- `codex-rs/memories/write/src/phase1.rs`、`prompts.rs`、`phase1_output.rs`：请求组装、模型预算、输出解析、无信号及失败结果。
- `codex-rs/state/src/runtime/memories.rs`：资格/更新时间、同 thread 替换、无输出处理、提炼与整合成功位置、重试及并发所有权。
- `codex-rs/memories/write/src/phase2.rs`、`storage.rs`、`workspace.rs`、`workspace_lock.rs`：摘要同步、来源变化 diff、写入所有权、成功基线与恢复。

固定源码入口：[该版本 Memory write](https://github.com/openai/codex/tree/8fdf6472955749a731fd9e4b8ffc218e8e80c51d/codex-rs/memories/write)；[state memory](https://github.com/openai/codex/blob/8fdf6472955749a731fd9e4b8ffc218e8e80c51d/codex-rs/state/src/runtime/memories.rs)。Nano 的取舍与保真验收只维护在 [design.md](../../design.md#上游保真与提示词适配)，不在此复制第二套设计。
