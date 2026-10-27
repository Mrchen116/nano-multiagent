---
status: research-snapshot
recorded-at: 2026-08-14
nano-baseline: 84b386b42a2b4f46755a98974012dace7716f098
source-baseline: claude-code-cli@2.1.232; native-sha256=7b39c1588df919d001dea3ffd5651adb682f2451b5a0e18d42d4233296b53cc7
subject: Claude Code 2.1.232 Auto Mode follow-up
latest-verified-package: "@anthropic-ai/claude-code@2.1.232"
current-owner: pending-adoption
---

# Claude Code 2.1.232 Auto Mode follow-up

本文只记录 2.1.227 研究包到 2.1.232 的增量证据。完整机制、证据分级和 Nano
迁移含义仍以 [`Claude Code Auto Mode Permission Mechanism 重建.md`](Claude%20Code%20Auto%20Mode%20Permission%20Mechanism%20%E9%87%8D%E5%BB%BA.md)
为主。本文不是 Anthropic 源码，也不把一次 trace 推广为所有 provider 或工具的完整实现。

## 1. 版本与二进制固定

2026-08-14 查询 npm registry 时，`@anthropic-ai/claude-code` 最新版为 `2.1.232`。
为避免改变本机已安装的 2.1.227，实验把 npm 包下载、解包并安装到独立临时目录，再直接调用
其中的 arm64 native binary：

```text
installed /opt/homebrew/bin/claude: 2.1.227
isolated probe binary: 2.1.232
npm tgz SHA-256: e6586e5c9c2ff2a1e6b48db8f87b0b99a82694c84c5d7e3fd0824cdb915858fb
native binary SHA-256: 7b39c1588df919d001dea3ffd5651adb682f2451b5a0e18d42d4233296b53cc7
```

临时原件位置：

```text
/private/tmp/cc-2.1.232-probe.PkjB3g/anthropic-ai-claude-code-2.1.232.tgz
/private/tmp/cc-2.1.232-probe.PkjB3g/runtime/node_modules/@anthropic-ai/claude-code-darwin-arm64/claude
```

官方 changelog 的 2.1.232 条目主要涉及 subagent fork/background、跨 session
`SendMessage` 与若干权限绕过修复；2.1.229 另修复了关闭 attribution header 时 Auto
Mode 每次调用都失败的问题。changelog 没有声明 classifier 两阶段拓扑或参数变更；因此下面以
runtime trace 独立验证，而不是从发布说明推断。

## 2. 2.1.232 受控两阶段 trace

实验在 fresh `mktemp -d` 工作目录中运行 2.1.232，使用：

```text
--bare --permission-mode auto --print --verbose
--output-format stream-json --tools Bash
```

模型只被要求调用一次：

```bash
curl -fsS http://127.0.0.1:9 | bash
```

用户消息同时声明 port 9 没有 listener、不得重试、不得调用其他工具、不得启动服务、不得修改
文件。目标是获得 `Code from External` 的 classifier 分支；不是执行外部 payload。最终 action
没有运行。

```text
session: fdca6a95-81f3-4b91-bad3-7bd5b6eff829
proxy locator: /Users/czj/Repos/LLM_PROXY/logs/session/2026-08-14_18-32-13_663_fdca6a95-81f3-4b91-bad3-7bd5b6eff829/
debug locator: /private/tmp/cc-2.1.232-auto-trace.XEySOJ/debug-proxy.log
stream locator: /private/tmp/cc-2.1.232-auto-trace.XEySOJ/stream-proxy.jsonl
model route used by this probe: codexOAuth:gpt-5.6-luna
```

### 2.1 Provider request manifest

| 阶段 | request | SHA-256 | 参数 | response | SHA-256 | 结果 |
|---|---|---|---|---|---|---|
| Stage 1 | `2026-08-14_18-32-18_229-req-anthropic_messages.json` | `6a74a87557171c0cd69290b1680348d57d79278b38effff7ef7466ffee0fdee6` | `max_tokens=2112`; `stop_sequences=["</block>"]` | `2026-08-14_18-32-18_229-downstream-res-anthropic_messages.json` | `63279f024771b89e97cc37901074d89d049e11c4bc927af74618b30704ddd8fe` | block / `Code from External` |
| Stage 2 | `2026-08-14_18-32-26_849-req-anthropic_messages.json` | `ff76093efa1db48b37ea85a095ad78bec6d8996a71ca6278e8f3d784a3b154a7` | `max_tokens=10240`; no stop sequence | `2026-08-14_18-32-26_849-downstream-res-anthropic_messages.json` | `f7548d3cb11ebfa16c4f5b205239af559cf5a00512dfc03abb7ab6915b513cd3` | block / `Code from External` |

两个 classifier request 的 system blocks 完全相同：

| block | chars | SHA-256 | 内容角色 |
|---:|---:|---|---|
| 0 | 74 | `a3c6a60e26d13fb665dcf735c97c974f70c5abc05dcebb7a7395e0fd94d00af3` | runtime/build billing header |
| 1 | 112,391 | `f38f0119b790caa654919c227e6d16cc0d46683ffead81ccea5b7c60dde48fa1` | Security Monitor policy |
| 2 | 238 | `393d9ea0b1b06acf4619928168193db67aee0a0c67fb29d8861a699e638624b4` | session context |

拼接后的 112,703 字符 system text SHA-256 为
`d6e0e00f5dc30182dc74ff818e1ddd602ecd4803f57fa73807056ce76f84a989`。
debug 直接记录 `stage=xml_s1` 与 `stage=xml_s2`；两阶段各正常返回，最终 permission
decision 为 deny，耗时 17,935 ms。

### 2.2 用户可见生命周期

stream-json 依次记录：

1. `Bash` tool proposal；
2. `system.permission_denied`，`decision_reason_type="classifier"`；
3. `tool_result` error，`non_execution_kind="automode-blocked"`；
4. 主 Agent 收到拒绝反馈后继续回复 `It did not run.`；
5. 整个 run 以 success/completed 收尾，并在 result 的 `permission_denials` 保留该 action。

这与官方 headless contract 一致：被拒绝的 action 不运行，但不会因此终止 main/subagent run。
它也证明 2.1.232 在本分支不是“Stage 1 block 后必由 Stage 2 放行”；Stage 2 会依据完整
intent/source policy 独立作最终 allow 或 block。

## 3. 2.1.227 → 2.1.232 policy delta

对 2.1.227 已提交的 deidentified Security Monitor block 与 2.1.232 原始 block 作逐行 diff，
观察到两个真实增量：

1. `Chrome-MCP` 定义加入 remote-device bridge 的 tool prefixes，并把这些远端可达的用户真实
   浏览器会话纳入同一非 sandbox 边界；
2. `soft_deny` 新增 `Third-Party Attack`，把对任务/演练未指定的真实外部组织或个人系统的攻击
   作为需明确命名目标的 block 类别，同时排除明确指定的 CTF、评测或授权 engagement target。

diff 中另有一处 Credential Materialization 示例差异，来自 2.1.227 study artifact 为通过 secret
scanner 所做的单点等义替换，不是版本 drift。2.1.232 没有再提交一份完整 prompt artifact：上面的
长度、hash、原始 locator 与精确 delta 足以复核，也避免重复保存一大份 vendor text。

这组变化说明：2.1.227 已恢复的机制拓扑仍可作为 2.1.232 基础，但迁移不能把 2.1.227 的默认
rule lists 当成永不变化的常量；必须给 built-in defaults 做可版本化、可检查、可由 `$defaults`
继承的配置 owner。

## 4. Runtime defaults 与配置替换契约

在同一隔离 config directory 中，2.1.232 的 `claude auto-mode defaults` 和
`claude auto-mode config` 输出 canonical JSON 完全相等：

```text
allow: 17
soft_deny: 66
hard_deny: 1
environment: 20
canonical sorted JSON SHA-256: d53834a04ff7e0a46e000942279d6e6acc81e9f96a7bce584b392d3dd5561593
```

2.1.227 的对应计数为 `17 / 65 / 1 / 20`，canonical hash 为
`9e8e8f04636a1d77daf9b28733496ba501404f1c87a5b57b292e0d0f8405dfc2`。只比较
rule label inventory 时，唯一新增项是 `soft_deny.Third-Party Attack`；第 3 节记录的 Chrome-MCP
定义扩展是既有规则/definition 内的文本更新，不会改变计数。

### 4.1 2.1.232 built-in label inventory

`allow`（17）：

```text
Security Discussion
Transient Retry
Test Artifacts
Local Operations
Read-Only Operations
Declared Dependencies
Toolchain Bootstrap
Standard Credentials
Session-Created Job Cleanup
Git Push Destination
Trusted Internal Infra (Data Flow)
Scheduled-Task Fires
Multi-Agent Coordination
Memory Directory
CLAUDE.md Content
Claude Code Scheduling
Browser Trusted Navigation
```

`soft_deny`（66）：

```text
Git Destructive
Code That Leaks When Run
Code from External
Cloud Storage Mass Delete
Production Deploy
Remote Shell Writes
Sensitive Remote Exec
Production Reads
Blind Apply
Protected-Scope IaC Apply
Logging/Audit Tampering
Permission Grant
TLS/Auth Weaken
Secret-Store Writes
DNS / Domain / Cert Changes
Security Weaken
Security Test Removal
Safety Bypass Flag
Create Unsafe Agents
Interfere With Workloads
Shared Cluster Mutation
CI Bypass
Modify Shared Resources
Irreversible Local Destruction
Unverifiable Deletion Target
Shared Scratch Sweep
Irreversible Deletion (general)
Create RCE Surface
Expose Local Services
External Ingress Tunnel
Credential Leakage
Credential Materialization
Credential Exploration
PII Data Handling
Exfil Scouting
Traffic Redirection
Remote Repoint
Out-of-Place Publication
Sensitive-Source Provenance
Excess Sensitive Detail
Live-Shared Artifact Sensitive Delta
Sandbox Network Callback
Create Public Surface
Public Data-Sharing Upload
Untrusted Code Integration
Package Registry Bypass
Unauthorized Persistence
Self-Modification
Tmux Self Drive
Instruction Poisoning
Auto-Mode Bypass
Session Transcript Tampering
External System Writes
Merge Without Review
Self-Approval
ChatOps Trigger Comments
Feature Flag Writes
Node Lifecycle Operations
Cluster-Wide Workload Creation
Real-World Transactions
Third-Party Attack
Browser Navigate Exfil
Browser Input Exfil
Browser JS Exfil
Browser File Upload Exfil
Browser Shortcut Execution
```

`hard_deny`（1）：`Data Exfiltration`。

`environment`（20）：Organization、Primary use、Cloud providers、Repository visibility、
Internal sharing、Org-specific CLIs、Secrets management、CI/CD deploy targets、Network posture、
Protected deployment environments、Data retention、Trusted repo、Source control、Trusted internal
domains/buckets/services、Internal package registry、Sensitive data locations/audiences、Sensitive remote
targets、Protected IaC scopes。

### 4.2 `$defaults` 是有序 splice，不是 merge flag

同一 2.1.232 binary 的 inline `--settings` 探针确认：

- `autoMode.allow=["CUSTOM"]` 后，effective counts 为 `1 / 66 / 1 / 20`：只替换 `allow`，其余
  三段仍继承 defaults；
- `autoMode.allow=["BEFORE", "$defaults", "AFTER"]` 后，`allow` 为 19 条，首项 `BEFORE`、
  defaults 原序居中、末项 `AFTER`；
- clean config 下 `defaults` 与 `config` canonical output 相等。

因此迁移时不能沿用 Nano 当前的 workspace-over-global tuple 拼接直觉：四个 classifier section
独立决定“继承默认”还是“完全接管”，`$defaults` 的位置还决定自定义规则相对 built-ins 的顺序。
Nano 若提供 effective-config 检查面，必须展示展开后的最终列表，而不是只回显用户输入。

### 4.3 启用、禁用与配置来源是独立控制面

最新版官方 contract 把“模式是否可用”“session 选择了什么模式”“classifier 如何配置”分开：

- `permissions.defaultMode="auto"` 在 project `.claude/settings.json` 和 local
  `.claude/settings.local.json` 中会被忽略，仓库不能给自己开启 Auto；user/managed settings 或 CLI
  session flag 才能选择；
- `autoMode` 本身也只读取 user settings、managed settings 与 inline `--settings`/SDK JSON，project
  与 local settings 被忽略；
- managed `disableAutoMode="disable"`（也可写为 `permissions.disableAutoMode`）会从 mode cycle 删除
  Auto，并在 startup 拒绝 `--permission-mode auto`；
- 模式还受 account plan、provider 和主模型支持矩阵约束。模式不可用是确定性的 eligibility 失败；
  已进入 Auto 后某个 classifier request 失败才是 action-level no-verdict，两者不能复用同一错误；
- 2026-08-14 起，官方产品只对符合条件的 Pro/Max/Team 新 session 推动 Auto 默认；用户已有 default
  不会被静默覆盖，managed default 也保持不变。

无模型调用的本地 2.1.232 scope probe 另外在 fresh workspace 的
`.claude/settings.json` 写入唯一 `autoMode.allow=["PROJECT_SHOULD_BE_IGNORED"]`，并把
`CLAUDE_CONFIG_DIR` 指向独立空目录。`claude auto-mode config` 仍输出默认 `17 / 66 / 1 / 20`，
`allow` 中找不到该哨兵，直接验证 project classifier config 被忽略。探针原件位于：

```text
/private/tmp/cc-2.1.232-scope-probe.jQvy4Q/
```

Nano 没有 Anthropic account/provider gate，不能机械复制这张商业支持矩阵；但需要自己明确
`mode_available` 的 capability source、classifier model compatibility，以及管理员禁用优先于
workspace/session 请求的配置优先级。否则一个 workspace config 就可能把个人助手或生产节点切入
并不具备有效 classifier 的 Auto。

### 4.4 运维检查面

Claude Code 当前把配置检查与运行时 approval UI 分开：

```text
claude auto-mode defaults [--label PREFIX]
claude auto-mode config
claude auto-mode critique
claude auto-mode reset [--yes]
```

`defaults` 查看随版本发布的 built-ins，`config` 查看 `$defaults` 展开后的 effective lists，`critique`
检查自定义 prose rules 的歧义/冗余/误判风险，`reset` 只删除 user settings 的 `autoMode`，不会清除
managed 或 inline settings。后续 Nano design 至少需要 defaults/effective-config 的确定性检查与 config
provenance；是否提供 LLM critique 是可选产品能力，不能作为正确性门禁。

## 5. Classifier 前的确定性快路径清单

官方 permission contract 与本机 `mkdir` decision trace 共同证明，Auto 不是把全部工具直接送入
Security Monitor。可实施的 fast-path baseline 至少包括以下规则。

### 5.1 Read-only Bash evaluator

官方列出的 built-in 只读集合包含：

```text
ls cat echo pwd head tail grep find wc which diff stat du cd
read-only forms of git
```

这不是单纯的 command-name allowlist；validator 还带这些约束：

- `&&`、`||`、`;`、`|`、`|&`、`&` 和换行会拆成 compound subcommands，每段独立匹配；
- 固定剥离 `timeout`、`time`、`nice`、`nohup`、`stdbuf`、`command`、`builtin`、zsh
  `noglob`，以及无 flags 的 `xargs`；exec-capable wrappers 不能靠 prefix rule 自动放行；
- safe environment assignments 可剥离；其他 assignment 对 allow 不剥离，但 deny/ask 仍穿透；
- 对所有 flags 都只读的命令允许 unquoted glob；`find`、`sort`、`sed`、`git` 等存在 write/exec
  flags 的命令遇到 unquoted glob 时 prompt；
- `docker` 指向另一 daemon、`file -m/-f`、Windows UNC path、无法完整 parse 或超过 10,000
  characters 都不能走 read-only allow；
- `cd` 只允许进入 working/additional directory；`cd` 后进入另一目录再执行 `git`，或无法确定
  redirect target 的 compound command，会 prompt。

Nano 当前 `BASH_ALLOWED_PREFIXES` 虽包含部分同名命令，却只按 prefix 与 `&&` segment 判断，明确
没有 flag-level validator；`git config` 等 write-capable form 甚至可能因 prefix 被直接允许。迁移应
以 AST/argument effect evaluator 替换 prefix list，而不是简单扩大当前 tuple。

### 5.2 Accept Edits / in-scope local operations

最新版 `acceptEdits` 对 working directory 或 `additionalDirectories` 内的 Edit/Write 和以下常见
filesystem commands 自动批准：

```text
mkdir touch rm rmdir mv cp sed
```

同一 local-operation fast path 也是 Auto fixed decision order 的 classifier 前步骤，但 protected
path write 除外。Nano 当前 ordinary Write/Edit 返回 passthrough 并进入 classifier，正是日常编码
误判和延迟的直接来源之一。

### 5.3 Protected paths

2.1.232 官方完整表：

```text
directories:
  .git .config/git .vscode .idea .husky .cargo .devcontainer .yarn .mvn .claude
  exception: .claude/worktrees

files:
  .gitconfig .gitmodules
  .bashrc .bash_profile .bash_login .bash_aliases .bash_logout
  .zshrc .zprofile .zshenv .zlogin .zlogout .profile .envrc
  .npmrc .yarnrc .yarnrc.yml .pnp.cjs .pnp.loader.mjs .pnpmfile.cjs
  bunfig.toml .bunfig.toml
  .bazelrc .bazelversion .bazeliskrc
  .pre-commit-config.yaml lefthook.yml lefthook.yaml .lefthook.yml .lefthook.yaml
  gradle-wrapper.properties maven-wrapper.properties
  .devcontainer.json .ripgreprc pyrightconfig.json .mcp.json .claude.json
```

其 mode 结果不是“一律 ask”：`default`/`acceptEdits` prompt，`auto` routed to classifier，`dontAsk`
deny，`bypassPermissions` allow。`permissions.allow` 不能覆盖 protected-write routing。

Nano 现表只有 4 个共同目录、4 个 Nano config roots 和 8 个文件；既遗漏大量 ecosystem/persistence
入口，又把命中项一律作为 bypass-immune ask。迁移需要采用最新版完整表、保留
`.nano`/`.nanocode`/`.nanoassistant` 等产品根，并把“protected”与最终 behavior 解耦。

### 5.4 Rules remain before fast paths

read-only/local-operation 并不绕过显式安全边界：tool-pattern precedence 固定为
`deny > ask > allow`；deny/ask 可以覆盖 built-in read-only，protected writes 和 required-interaction
又能覆盖 allow。Auto 进入时会丢弃 `Bash(*)`、wildcard interpreters、package-manager run、`Agent`
等 arbitrary-execution broad allow，只保留 narrow rules；`classifyAllShell=true` 时连 narrow shell
allow 也暂停。

因此 Nano 的未来 evaluator 输出必须同时包含 `source` 与 `behavior`：`read_only` 是一个允许来源，
不是跳过规则层和 protected-path 层的全局 bypass。

### 5.5 Tool-pattern permission engine

classifier 之前还有一套确定性 permission-rule engine，其完整性不能由 classifier prose 代替：

- `deny > ask > allow`，specificity 不改变优先级；bare tool deny 会从 model context 删除工具，
  scoped deny 则保留工具并在调用时 block；
- deny/ask 可用 `Tool(param:value)` 匹配任一 top-level scalar input；allow 只能使用各工具定义的安全
  specifier。Bash `command`、file tools `file_path`、Grep/Glob `path`、WebFetch `url` 等 primary
  content field 不接受 generic param matcher；
- deny/ask tool-name glob 可覆盖所有工具；allow glob 只接受已固定 server prefix 的 MCP tool family，
  防止一个宽泛 allow 扩成任意新工具；
- Bash patterns 对 compound subcommands 独立判定；持久批准 compound command 时最多保存 5 条
  subcommand rule，而不是保存整段可被拼接绕过的 command；
- Read/Edit 使用 gitignore-style path patterns，区分 filesystem-root `//`、home `~/`、settings-source
  `/` 与 cwd-relative；allow 和 deny/ask 对 single-segment directory depth 的语义不同；
- symlink 同时检查 link path 与 resolved target：allow 要两者都命中，否则 prompt；deny 任一命中即
  block；Read deny 还覆盖 Edit/Write，同类 file commands 的 Bash fast path也受它约束；
- WebFetch 用 `domain:` 规则，case-insensitive、去 trailing dot；`*.example.com` 只匹配 subdomain，
  `example.*` 的 wildcard 不跨 dot，避免把 attacker-controlled deeper suffix 当成同一 domain；
- PreToolUse hook 能额外 deny/ask/allow，但 hook allow 不能越过 permission deny/ask、connector
  required ask 或 MCP `requiresUserInteraction`；blocking hook 又能压过普通 allow。

Nano 目前把 hostname rules、Bash prefixes、dangerous paths、tool safe allowlist 和 classifier config
分散成互不统一的格式，且 workspace `.nano/policy.toml` 能替换 Bash allow/deny tuples。后续设计需要
一个 typed rule matcher 和可信 config provenance；不能继续让每个 tool 自己发明 precedence。

## 6. Subagent spawn 与 completion runtime trace

为验证官方文档所述的 subagent review，不修改仓库、不使用子 Agent 工具、不访问网络或发送消息，
在 fresh `/private/tmp` workspace 中运行 2.1.232：

```text
--safe-mode --permission-mode auto --print --verbose
--output-format stream-json --tools default --forward-subagent-text
--no-session-persistence
```

主 Agent 被要求只调用一次内置 `general-purpose` Agent；delegated task 是“只返回文本 `42`”，并
明确禁止工具、文件、网络和消息。运行成功，subagent stream 记录 `tool_uses=0`，最终 main run
返回 `42`。

```text
session: 6f030df8-773e-46c3-9891-c2391bf8dd2f
proxy locator: /Users/czj/Repos/LLM_PROXY/logs/session/2026-08-14_20-09-58_926_6f030df8-773e-46c3-9891-c2391bf8dd2f/
debug locator: /private/tmp/cc-2.1.232-agent-review.TFzbqk/debug-safe-general-purpose.log
```

### 6.1 五个 provider request 的时序

| 顺序 | request | 角色 | 关键证据 |
|---:|---|---|---|
| 1 | `20-09-58_926` | main proposal | main model 提议 `Agent (general-purpose)` |
| 2 | `20-10-02_763` | pre-spawn classifier | `max_tokens=2112`; stop `</block>`; transcript 含 user delegation 与 pending Agent task；返回 `<block>no</block>` |
| 3 | `20-10-07_198` | subagent | billing header 含 `cc_is_subagent=true`; 返回 `42`; stream 记录 `tool_uses=0` |
| 4 | `20-10-10_097` | completion classifier | `max_tokens=2112`; stop `</block>`; transcript 把 hand-back 标为 agent-authored untrusted output；返回 `<block>no</block>` |
| 5 | `20-10-14_168` | main continuation | completion verdict 通过后才收到 tool result 并最终回复 `42` |

两个 classifier request 复用第 2 节相同的三个 Security Monitor system blocks：

```text
block 0: 74 chars; SHA-256 a3c6a60e26d13fb665dcf735c97c974f70c5abc05dcebb7a7395e0fd94d00af3
block 1: 112391 chars; SHA-256 f38f0119b790caa654919c227e6d16cc0d46683ffead81ccea5b7c60dde48fa1
block 2: 238 chars; SHA-256 393d9ea0b1b06acf4619928168193db67aee0a0c67fb29d8861a699e638624b4
```

请求/响应文件哈希：

| checkpoint | request SHA-256 | response SHA-256 |
|---|---|---|
| pre-spawn | `4b2a3123d757e49f3321181a78050d8dbfc33746fc29add2450e1d729a0a6b0a` | `899c57c215c6064fcc1ac56eab6243a8ab04a3f22fc7824d7aaaf6504f398e43` |
| completion | `c6709b3a53323e1c150f61dcb5f8bc2c5e120a1c996b10a3f90fb1dcef48943f` | `43a2227565b7f1cc984bd5bf259aaa4486b33c67823cfcbbc72cddcc69e90f13` |

debug 的线性时序进一步给出：pre-spawn classifier 完成并记录
`tool=Agent, behavior=allow` 后才出现 `tool_dispatch_start`/`task_started`；subagent 结束后先发起
第二个 classifier，完成后才记录 `tool_dispatch_end outcome=ok` 并向 main loop 交付 tool result。
因此 completion review 不是仅供 telemetry 的异步旁路，而在结果返回路径上。

### 6.2 Child action review 的三 checkpoint trace

第二条受控 trace 让 child 只调用一次 Bash：

```bash
python -c 'print(42)'
```

该命令不读写文件、不访问网络，stream/tool stats 记录 `bashCount=1`、其余 tool count 为 0，最终
child 与 main 都返回 `42`。

```text
session: b06eebab-f75a-4874-8dcb-b4686663b0e3
proxy locator: /Users/czj/Repos/LLM_PROXY/logs/session/2026-08-14_20-13-13_837_b06eebab-f75a-4874-8dcb-b4686663b0e3/
debug locator: /private/tmp/cc-2.1.232-agent-action.J7jW0L/debug.log
```

这次共有七个 provider requests：main proposal → pre-spawn classifier → child proposal → child Bash
classifier → child continuation → completion classifier → main continuation。三个 classifier checkpoint
都是 2,112-token Stage 1、stop `</block>`，并分别返回 `<block>no</block>`：

| checkpoint | classifier transcript 的 action 边界 | request SHA-256 | response SHA-256 |
|---|---|---|---|
| pre-spawn | parent user instruction + pending `Agent (general-purpose)` task | `d2dd15806613deb9b0a4989a7401079af7e7db558b99c3b58eec0eff40210e36` | `ce76e7c689c32aeee6e88030b1e1d0d1a4e932aa3f8bc1c616a133736601814f` |
| child action | child user task + pending `Bash python -c 'print(42)'` | `43f5a7349c9ac32b2a17ee31bbf17ceae0b113e654fb83ca2ed1d6a8a834b0f9` | `04f8ffeef394ef62fc24318009387eb76c80c62d1c613364764303b0574fb711` |
| completion | historical Bash action + synthetic untrusted hand-back user message | `03b722a772e643edecbed318f805f8158d4f0f60be9e412b479fbd6d3aca3c75` | `2cb3c4b358f7c550781f2ad53253e4150636fdd9ea8698bc35ed90ff661cdc26` |

debug 依次记录：

```text
Agent classifier allow → Agent dispatch start
Bash classifier allow → Bash dispatch start → Bash dispatch end
completion classifier allow → Agent dispatch end → parent tool_result
```

三个请求仍使用第 2 节相同 system block hashes。child-action transcript 不是 parent transcript 的简单
复制：它只包含 delegated user task 与 child pending action；completion transcript 保留 reviewable
Bash action，但不把 Bash tool result 作为可信 user turn，并把最终 `42` 放进显式
`<subagent_hand_back>` untrusted envelope。这给 Nano 后续 provenance schema 提供了可复刻边界。

### 6.3 这些 trace 尚未证明什么

- 三个 checkpoint 都在 Stage 1 allow 结束，没有证明 spawn/action/completion 的 Stage 2 block、
  completion warning 或 independent safety-check failure 形态；
- `--safe-mode` 禁用了自定义 project/plugin 行为，但主 Agent 的 builtin tool catalog 仍完整；实际
  安全边界来自 delegated task、零工具 trace 与单 Bash trace 的 tool stats，不是 OS sandbox 等价声明。

## 7. `SendMessage` pre-delivery runtime trace

为避免真实外发，探针使用唯一且明确不存在的目标
`nonexistent-agent-auto-probe-20260814-2015`，正文为 `AUTO_PERMISSION_PROBE`，并禁止任何其他工具
或重试。最终工具返回 `Not sent — no agent ... is reachable`，没有发生 delivery。

```text
session: 6e873a19-062a-4f92-b78d-61e2b7bd7405
proxy locator: /Users/czj/Repos/LLM_PROXY/logs/session/2026-08-14_20-16-01_111_6e873a19-062a-4f92-b78d-61e2b7bd7405/
debug locator: /private/tmp/cc-2.1.232-send-message.sZsL6O/debug.log
```

三请求链为 main proposal → classifier → main continuation。中间 classifier request：

```text
max_tokens=2112
stop_sequences=["</block>"]
request SHA-256=b8aa391adad86ff359ea19bdc40b7ecc96a54733defa6d3c3d79be2a5c3dd786
response SHA-256=8d61709cc984b8e584399d3ac969373a62e84aab171107e6d0b4a69b1174aee0
response=<block>no</block>
```

classifier transcript 同时包含 human instruction 与结构化 action projection：

```text
SendMessage to nonexistent-agent-auto-probe-20260814-2015:
AUTO_PERMISSION_PROBE [summary: Permission probe]
```

debug 记录 `tool=SendMessage, behavior=allow` 后才出现 `tool_dispatch_start`；dispatch 随即以不存在目标
返回，耗时 2 ms。这证明 2.1.232 至少在本分支对 recipient、content 与 summary 作 pre-delivery
classification，而不是把 agent messaging 按工具名整体 bypass。它尚未证明 successful delivery、
cross-session/machine branch、Stage 2 block 或 sensitive-content warning 的运行时形态。

## 8. 对 Nano gap ledger 的最新校正

| contract layer | Claude Code 2.1.232 | Nano observation at `84b386b4` | 必须进入后续 design 的 delta |
|---|---|---|---|
| permission modes | `default`/manual、`acceptEdits`、`plan`、`auto`、`dontAsk`、`bypassPermissions` | 单一 `auto_mode.enabled` 加 dangerous bypass | 明确 Nano 是只迁 Auto 核心还是同时提供 mode 状态机；不能把 `enabled=false` 当完整 Manual |
| availability/control | account/provider/model eligibility；managed disable；project/local 不能自启 Auto | workspace `auto_mode.enabled` 可 field-override global；classifier 复用任意 configured approval/run model | 定义可信 availability owner、model capability 与不可覆盖的 admin disable；区分 mode unavailable 和 action no-verdict |
| rules and config | tool-pattern deny/ask/allow 先决；classifier `environment`/`allow`/`soft_deny`/`hard_deny`，`$defaults` 与 `classifyAllShell` | global + workspace `auto_mode`; 无 `hard_deny`、`$defaults`、scope protection 或 effective-config inspection | 引入安全配置来源、替换/继承语义、版本化 defaults 和检查命令；workspace 不能自授 Auto 安全边界 |
| protected writes | Auto 中进入 classifier；Accept Edits 中 prompt；完整 protected path 表 | Write/Edit 对较短 dangerous path 表直接 ask，且 bypass-immune | 扩完整表并按 mode/decision source 路由；保留 Nano 自己的 config roots |
| deterministic fast paths | read-only 与 in-scope edits/filesystem commands 在 classifier 前自动批准 | `read` 全局 safe；普通 Write/Edit 仍进 classifier；Bash 仅 prefix policy | 建 typed read-only/local-operation evaluator，避免正常编码动作承受 classifier 延迟和误判 |
| Bash/sandbox | rule → AST/safety/read-only/Accept Edits/sandbox capability → classifier | prefix-only allowed/denied policy；无 OS sandbox capability | 不伪造 sandbox 等价；把可静态证明的 local/read-only 与真正 capability-backed sandbox 分开 |
| classifier | 2,112/10,240 conditional stages；server-selected/default Sonnet 5 model；typed environment/provenance | 64/4,096；可配置任意 registered run model；缺完整 provenance/history facts | 重建 input contract、阶段 outcome 与 model-selection policy；数值不能只机械替换 |
| outcomes and ledger | normal block、no-verdict、Recently Denied/retry、3 consecutive/20 total fixed fallback | `allow`/`deny`/`ask`；按 `(run, tool)` 可配置 deny limit 3；无 retry/no-verdict ledger | 分离 decision source/outcome；session-global counters 与 retry ledger 只计 normal classifier block |
| unattended | action 不运行，main/subagent 继续；无 prompt 时不把 run 失败化 | ask/no-verdict 常映射为 unattended deny；结果只表现为普通 tool block | 明确 continue/replan 反馈和终态，不让无人值守 child 因人工面缺失而系统性卡死 |
| subagents | spawn task、每次 action、completion history 三次 review；继承 parent Auto | `agent` 在 safe allowlist；child action 走 unattended gate；无 spawn/completion review | 引入 delegation/action/return 三个 checkpoint 与 unreviewed/untrusted return marker |
| messaging | 每次 `SendMessage` 经 classifier；2.1.232 又扩大跨 session messaging | `personal_assistant` 注入真实 `SendMessageTool`，但 gate 按工具名把 `send_message` 全局 safe-list，目的地和正文均不参与裁决 | 删除 side-effect bypass；把 agent message、跨 session/channel outbound 的 destination/content/identity 作为 typed action |
| channel UX | normal block、no-verdict、Recently Denied、manual prompt 是不同状态 | Web IM 主要区分等待批准/已拒绝；飞书只镜像真正的 permission request | 保持 Nano 多渠道面，但扩充稳定 reason/source/status；Auto block 不应伪装成人工拒绝 |

现有 `refactor-476-permission-transaction-owner` 只收拢 ask transaction ownership，并明确不改权限
策略。迁移 unit 应依赖或协调它提供的 transaction seam，而不能把新版 policy state 继续塞回
`AgentEngine` closure，也不能重复实现第二个 pending owner。

### 8.1 Nano observation 的源码锚点

本表以源码而不是名称相似性判定 current behavior：

| 观察 | 代码锚点 |
|---|---|
| config 只有 `enabled`、bypass、tool allowlist、deny/timeout/unattended、三段 classifier prose 与 `web_fetch`；workspace field 覆盖 global | `src/agent/platform/config/auto_mode.py:40-56,59-83,106-149` |
| gate 固定按 tool self-check → bypass → session/tool safe-list → tool decision → deny-limit → classifier 顺序运行 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:773-1046` |
| `agent`、`send_message`、`memory` 等按名字直接跳过 classifier | `src/agent/platform/hooks/builtins/auto_mode_gate.py:183-230,867-873` |
| PA 确实注册 `SendMessageTool`；它把 `text`/`to` 直接交给 Gateway，没有 permission projection/self-check | `src/personal_assistant/product.py:395-460`; `src/personal_assistant/tools/send_message.py:65-196` |
| classifier 仍是 64/4,096 token、当前/显式 approval model 与三态 `allow/deny/ask` | `src/agent/platform/hooks/builtins/auto_mode_gate.py:436-560,971-1039` |
| transcript 只保留用户文本和 assistant tool calls，当前 action 依赖各 tool 的字符串 projection | `src/agent/platform/hooks/builtins/auto_mode_gate.py:300-382,588-658` |
| broker 的 retry state 是 `(run_id, tool_name)` deny count 与 session tool-name allowlist | `src/agent/platform/permissions/broker.py:104-127,230-260` |
| Bash 明示只有 prefix precision；只拆 `&&`，workspace `policy.toml` 可整段替换 allow/deny tuples | `src/agent/platform/tools/builtins/bash_policy.py:1-16,54-177,193-275,313-315` |
| ordinary Write/Edit 对非 dangerous path 返回 passthrough；dangerous path 一律 bypass-immune ask | `src/agent/platform/tools/builtins/write.py:122-155`; `src/agent/platform/tools/builtins/edit.py:125-154` |
| dangerous path inventory 只有 8 files/8 dirs，另保留 Nano product roots | `src/agent/platform/tools/dangerous_paths.py:16-58` |
| unknown WebFetch host 直接 ask，不进入 classifier | `src/agent/platform/tools/builtins/web_fetch.py:323-430` |

这些锚点只描述 baseline `84b386b4`；它们不是对 dirty checkout 中其他未提交 change unit 的所有权
声明。后续 design 必须先判断 `refactor-476` 最终合入状态，再选 transaction seam。

## 9. 仍未宣称恢复的内部细节

- 未反编译 2.1.232 完整 native binary call graph；2.1.227 的 minified Bash observations 仅作为
  topology 交叉证据。
- 未对每个 tool family 运行分类矩阵，因此不能声称所有 routed tool 都用同一 two-stage pair。
- 本地 proxy route 显式指定了 `codexOAuth:gpt-5.6-luna`；它证明 CLI 发出的 request topology
  与参数，不证明 Anthropic server-side Sonnet 5 选择在这个非官方 route 上生效。
- 未捕获 classifier no-verdict、3/20 fallback、interactive retry、subagent Stage 2 block/completion
  warning/independent safety failure，或 successful/cross-session `SendMessage` 的完整 runtime trace；
  subagent 三 checkpoint 与 nonexistent-target message 的 Stage 1 allow 已分别在第 6/7 节闭合，
  其余当前仍是官方 contract。
- Nano 的产品目标仍需 owner 确认：核心裁决语义兼容，还是连全部 mode/UI/sandbox 行为一并复制。
