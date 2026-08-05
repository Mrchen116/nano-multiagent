# feat-503: As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- Base: `e6f8b617a7beb1dc68e1a116f368eaf05c764606`
- Head: 本 unit 首次实现提交前的 working tree
- Commits: 待首次实现提交
- Included dirty files: `config/e2e/`、`scripts/e2e*.{sh,py}`、`tests/e2e/`、`tests/unit/test_e2e_feishu_config.py`、`docs/development/`
- 受影响模块：worktree E2E launcher、Feishu 测试配置渲染器、外部 channel probe、critical-path test harness 与开发运行手册。

## 最终结构

### 组件与职责

| 组件 | 最终职责 |
|---|---|
| `config/e2e/gateway.yaml` | 唯一的、无密钥固定双 agent / Web IM / LLM catalog；声明默认禁用的 `feishu:e2e` channel |
| `scripts/e2e-up.sh` | 默认从仓库 profile 派生 worktree config；`--feishu` 选择专用拓扑且拒绝和 `--main-config` 混用 |
| `scripts/e2e_feishu_config.py` | 读取本机私有 env、验证 App 对应预期 Bot、只把凭据写入 worktree 副本并收紧权限 |
| `scripts/e2e-feishu-probe.py` | 验证命名的非 default CLI profile 与 App/Bot 一致，发送 nonce 并等待独立 saga store 的 ingress 证据 |
| E2E tests / docs | 让默认、stub 和 resilience 路径不再依赖个人 config，并说明实际 setup/cleanup 合约 |

### 调用链与数据流

```text
config/e2e/gateway.yaml + private feishu-e2e.env
        │  (Bot identity must match)
        ▼
e2e-up.sh --feishu → worktree .gateway-config.yaml → isolated Gateway → test Feishu Bot
                                                                     ▲
named lark-cli test profile → e2e-feishu-probe nonce ────────────────┘
                                                                     │
                                                      external_shadow_sagas.sqlite3
```

默认 `e2e-up.sh` 不走此分支，而是从 `config/e2e/gateway.yaml` 复制并继续使用既有的端口、IM identity、workspace、PID 和 cleanup 隔离逻辑。`--main-config` 保留为显式的特殊测试输入，不是默认回退路径。

### 状态、数据与兼容性

- App ID、App secret、Bot Open ID 和 CLI profile 名仅存在于 `${XDG_CONFIG_HOME:-~/.config}/nano-multiagent/feishu-e2e.env`；该文件权限为 `0600`，不在仓库内。
- 渲染后的 `.gateway-config.yaml`、channel credential/manifest、SQLite shadow saga 和日志均为 worktree runtime 数据，由 `e2e-down.sh` 处理且不得暂存。
- 固定 `e2e`、`e2e-peer` 两个 agent，覆盖内部 IM 双 Agent 群聊；当前唯一 Feishu Bot 绑定 `e2e`，外部群聊由测试用户与该 Bot 组成。
- 既有调用者仍可传 `--main-config`；默认和所有当前长期 E2E entry point 改为仓库固定 profile。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 默认 config 入仓且无密钥 | 消除个人机器配置漂移，同时不提交可用凭据 | `config/e2e/gateway.yaml`, `scripts/e2e-up.sh` |
| Feishu channel 默认禁用、运行时注入 | 一份固定拓扑避免配置漂移；默认不连外部平台，敏感值只出现于运行副本 | `config/e2e/gateway.yaml`, `scripts/e2e_feishu_config.py` |
| 启动前核对 Bot identity | 错放生产 App 凭据时在连接前失败 | `render_feishu_config()` |
| probe 强制命名非 default CLI profile | 避免 `lark-cli` 默认 profile 指向另一 App/Bot；没有 UI fallback | `scripts/e2e-feishu-probe.py` |
| ingress saga 是 readiness 证据 | 它直接证明平台消息到达本次 isolated Gateway，不把 LLM 上游慢/失败误报为 Feishu listener 故障 | `_saga_count()` |

## 失败路径、风险与回滚

- 私有 env 缺失、格式错误、App/Bot identity 不一致：launcher 不会启动 Feishu listener；修正本机私有 profile 后重试。
- CLI profile 未验证、为 default、或跨 App/Bot：probe 在发送前失败；重新登录命名测试 profile。
- nonce 未写入 saga：probe 有界超时并失败；保留 worktree 日志和 runtime DB 排障，随后执行 `e2e-down.sh`。
- 外部平台或 LLM 上游不稳定：probe 只断言 ingress；需要产品回复的 unit 在自己的验收中另行验证，不能把上游故障归因给 channel。
- 回滚：移除本 PR 后现有显式 `--main-config` 调用仍可用；不需要修改生产 Bot 或个人 Gateway config。

## 与初始意图的差异

无。实现遵循用户确定的“仓库固定测试 config + 专用测试 Agent 登录 + 独立 PR”边界。根目录错误 `.env` 已移入废纸篓，不再被 E2E 读取。

## 验证定位

- 用户验收：用户明确授权专用测试 Bot 的真实外部动作；本 PR 的真人开发入口由用户后续在 review 时复查，不伪造已完成的个人体验确认。
- 自动化测试：`tests/unit/test_e2e_feishu_config.py`；`tests/unit/test_e2e_catalog.py`；`tests/e2e/test_worktree_stack_lifecycle_e2e.py`；`tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py`；`tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py`。
- 运行证据：专用 profile 的真实 nonce probe 已在本 worktree 通过，并新增一条 durable external shadow saga；测试 listener 已由 `e2e-down.sh` 关闭。

## Canonical 文档影响

- Delta-spec：无。
- 归并目标：`docs/development/worktree-runtime.md` 与 `docs/development/e2e-critical-paths.md` 已直接更新。
- 若无产品 canonical spec 变更，原因：本 unit 改变开发/验收基础设施，不改变产品对最终用户的行为契约。
