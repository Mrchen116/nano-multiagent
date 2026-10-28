# refactor-675: Air 与 Mini 同时开发 — 技术方案

> 对齐 [motivation.md](motivation.md)。用户已确认生产隔离、共用 skill、本机配置、Air 独占现有飞书测试号与手动部署；以下是这些决定的实施细节。

## Changelog

## 现状分析

### 涉及范围

`scripts/e2e-up.sh` 负责临时服务与配置，`e2e-down.sh` 负责清理；仓库默认测试模型配置在 `config/e2e/gateway.yaml`。开发路径和观测入口由 AGENTS.md/development 文档提供；生产接线由 prod-fleet 及部署 skill 维护。

### 既有约束

不改业务包/DSH，不共享生产凭据给测试；保留主仓无关提交。正式服务只做必要迁移和有限只读核对。现有编号、spec/design main 提交流程继续，实施独立分支和 PR，合并仍由用户决定。

### 可复用能力

复用 E2E 的端口、身份、workspace 隔离与 daily profile，飞书复用现有 Air 私有文件和本机锁。复用 Gateway CLI 生成 LaunchAgent。复用 Tunnel supervisor，不修改其代码/网络路径。复用现有 Python 环境管理，不建立配置中心、跨机锁或新平台。

### 相关历史

feat-667 部署 SHA `4cea0166d` 是本次 Mini 同版本迁移基线；后续 main 业务提交不随此次迁移上线。Air 已使用固定 prod-main。refactor-668 的 recording provider 测试继续独立于真实模型验收。

## 架构总览与关键决策

1. **两机共用仓库内容，本机使用一个私有 JSON 文件。** 默认 `${XDG_CONFIG_HOME:-~/.config}/nano-multiagent/dev-host.json`，可由 `NANO_DEV_HOST_CONFIG` 指定绝对路径。无配置时保留社区/CI 的现有默认 E2E 行为；显式指定但缺失或格式错误则失败。它是开发辅助输入，不进入产品配置、Git 或模型系统 prompt。
2. **使用完整本机 E2E 源配置，避免叠加产品配置规则。** `e2e_config` 可选路径，为私有的仓库测试模板副本；Mini 只修改 LLM endpoint 和非秘密 placeholder key，不从生产 config 复制节点/身份/密钥。默认 daily/feishu 也使用这份源配置再执行既有 profile 转换。显式 `--main-config` 继续仅支持 default 且优先。
3. **在产生副作用前保护生产目录。** 私有 `protected_paths` 包括两机生产 checkout/数据；源 checkout 和 `--wt` 目标均规范化真实路径。任何目标/源位于保护目录内，或目标作为祖先包含保护目录，均拒绝 up/down。生产 checkout/data 额外放 `.nano-production` 标记（Git 本机 exclude），读取祖先标记，防遗漏本机配置。检查在删文件、复制 config、停止进程之前完成。防止误操作，不把开发者本机配置视为安全权限边界。
4. **飞书按机器能力显式分工。** `feishu_e2e` 为可选布尔，Air true、Mini false。false 时 up 的 `feishu` profile 在读取凭据/锁前拒绝；不改变其他现有 profile 的契约。Mini 不提供该 Bot 的环境文件。未来若独立 Bot 准备好再修改本机能力。
5. **Mini 生产与开发彻底分开。** 使用固定 detached `~/.nanoassistant/prod-main/nano-multiagent`（普通 Git worktree），IM 数据在 `~/.nanoassistant/im-data/`。Tunnel 的 Python 环境在 `~/.nanoassistant/runtime/tunnel-venv/`；依赖按现有环境的实际版本安装。Node 保持已安装固定运行时。配置、密钥、DSH state、agent workspace 保留原位置。
6. **保持轻量编号协作。** 新建前 fetch 并基于最新 main；取号后尽快提交首文档。非 fast-forward 时重新 fetch，检查全 type 的 active/archive/retired 同数字目录；无撞号可重放本 unit 文档后再推，有撞号则本地未发布 unit 重新取号并更新引用。设计继续原 unit。已发布的编号不可重分配，不 force-push。

## 接口与数据流

新增 `scripts/dev_host.py`（Python 标准库）：

- `check`：输出配置路径、是否存在、host 标签、开发命令路径及本机能力/日志根目录，检查所声明配置/目录是否存在。报告不输出 Gateway YAML 或任何密钥值。缺失可选日志标明不可用；明确区分“路径存在”与真实 E2E 通过。
- `guard --repo PATH --runtime PATH [--profile default|daily|feishu]`：载入本机设置、真实路径检查与 profile 能力检查，成功零退出，失败给具体可行动原因。
- `e2e-config --repo PATH`：返回本机测试 YAML 路径或仓库默认。仅供脚本取得文件路径，错误非零退出。

配置字段限定：`host`（展示标签）、`e2e_config`、`protected_paths`（绝对路径数组）、`feishu_e2e`、`llm_logs`（本机日志根目录）、`reference_root`（可选参考仓根目录）。示例放 `config/dev-host.example.json`，不引入配置生成器或自动发现生产秘密。

up 在解析参数后先 guard，随后选择源 YAML；down 在停止任何服务前 guard。本机文件路径允许 `~` 展开；无 host 配置时的 guard 仍检查生产标记。用户仍通过正常 `pnpm`/Python 工具工作，check 不安装依赖、不发模型请求、不修改服务。

## Agent Context

Consumer 是运行 change-* 的开发 Agent。Before：默认假设 Air 的代理日志和路径；After：AGENTS → 本机开发说明 → `dev_host.py check` 与本机文件，按需取得当前机器信息。角色/门禁语义保持，生产部署 skill 明确 Air 手动发起及固定生产 checkout。机器切换后重新读当前配置，历史路径不能作为本机事实。

将 AGENTS.md、local-development、worktree-runtime 和 llm-integration 链接到同一权威的本机配置说明；删除通用入口里的 Air 绝对路径假设。部署事实仍以 prod-fleet 为权威。独立 reviewer 实际读取这些入口并在 Air/Mini 各跑 check，核对其下一步能找到正确模型入口、隔离目录和飞书限制；无需为文档改动发起业务模型任务。真实隔离栈验证配置消费和一条合成模型回包，不能仅凭配置文件存在宣称可开发。

## 契约层增量

no spec delta：不改变 Gateway/IM 产品行为或公共 CLI。开发运维工具和工作流约束归并 development/operations，不在产品 specs 重复维护。

## 风险与回退

风险集中在 Mini 服务引用与数据路径迁移；遵循 [deployment-prompt.md](deployment-prompt.md)。本机配置错误应在起栈前明确失败。不建立跨机器编号锁，极少数同时新建冲突按推送先后处理。

## 一次性部署迁移

见 [deployment-prompt.md](deployment-prompt.md)。设计期间不改生产；实施验证完成后按已确认的迁移范围迁出 Mini，保持原 SHA。后续代码版本更新仍须用户在 Air 发起。

## Runbook for Reviewer

无新增常驻服务，零产品用户面，不派产品 reviewer。静态 code review/verifier 核对开发命令真实执行证据和有限迁移结果。

实施时在 Air 的本 unit worktree、Mini 的独立同 SHA 开发 worktree 分别准备依赖：`pnpm install --frozen-lockfile && pnpm build`、前端 `npm ci`，本机 `.venv/bin` 加入 PATH。运行 `python3 scripts/dev_host.py check`；真实隔离服务用 `scripts/e2e-up.sh --profile daily --wt <该机隔离目录>`，停止用匹配的 `e2e-down.sh --wt …`。一次合成 API 聊天与回包证明模型路由，无飞书测试写入。保护目录拒绝和 Mini 飞书拒绝只验证提前失败，不启动服务。

前置：Air 既有 LLM_PROXY，Mini 既有 LLM_Bridge；已用只读生产配置确认二者的地址，不复制生产 config。新测试工作区及账号使用既有 E2E 机制。迁移完整性/失败恢复采用临时 SQLite 与附件目录副本演练，不使用生产注入故障。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-development | 两机开发隔离与一次性迁移 | 无 | 单组 | dev_host、E2E 入口、测试、开发/部署文档、两机本机配置和 Mini 迁移 | [reviewer] 零产品用户面，无产品 reviewer；[worker] 保护目录含 symlink/祖先保护、错误配置和 Mini 飞书提前拒绝的窄测试通过；Air/Mini check 与 daily 真栈、合成模型回包成功并清理自建服务；临时 SQLite/附件复制、重入识别、切换失败恢复演练通过；Mini 同 SHA 迁移数据完整、服务路径与只读健康通过；独立 Context/代码/一致性审查通过，相关本地 CI 与远端 CI 通过；无生产消息测试、安装包发布或自动部署。 |
