# bugfix-819-desktop-windows-host-resilience: Review

## 范围与版本

- 本次问题与需求/设计位置：[fix.md](fix.md)（覆盖 Issue B 回环防缓存与 WebView 升级缓存清理、Issue C/D 主窗口创建容错与 Windows 前台激活及生命周期死锁回收、Issue E 解包前磁盘可用空间预检与精准错误分类、Issue F Windows 彩色托盘图标），关联契约 [desktop-client.md](../../../specs/im/desktop-client.md)、[service-lifecycle.md](../../../specs/gateway/service-lifecycle.md)。
- 实际 executed_base / validated_at：`executed_base = 890d74f70d1444f2fd961a7e60d02b858821abaa`（`origin/develop`）；首轮 `validated_at = 045158d0796bd7cfaec4672898e2ffdecff0c798`，修复后独立复验 `validated_at = 5488d9ec1e219e2fb8b2768edc291b1314a2ca00`，Windows CI 清单嵌入补丁独立增量复核基于 `ad8d5b2993ce958155420bc3d3b2e0ef90175d39` 工作树改动。
- 最终 effective_base / effective_through 与保留依据：`effective_base = 890d74f70d1444f2fd961a7e60d02b858821abaa`；远端 `ad8d5b299` 跑通 8/9 项检查后，针对 `windows-x64` `--lib` 测试缺少 `Common-Controls 6.0.0.0` 清单导致的 `0xc0000139` 补充 `apps/desktop/build.rs` 链接器清单嵌入及条件编译告警清理，已由同一独立审查者完成 `patch` 复核（`pass`，0 新增 finding），既有代码、测试与契约校对结论完整保留有效。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| G1-1：4 类缺陷修复完整性、Win32 FFI 安全、并发锁竞态与既有不变量保持 | `change-code-review`（独立审查者 [Independent Code & UX Reviewer](conversation://f73e7a1d-992c-462f-b09f-1dad362a4cf6)，full + patch/closure） | `pass` | 审阅全部受控变更及上下游调用方；首轮检出 2 项锁回收竞态与 1 项错误码边界问题，已在 `5488d9ec1` 修复并经独立复验确认关闭；`cargo test --locked`（22 passed）、`vitest`（11 passed，含 4 路并发抢锁 + `signal-exit` 残留跨越 1.4s 心跳验证）与 `node-lifecycle.mjs` 全部通过。 |
| G1-2：首次准备页三态信息层级、文案自明性与双平台托盘图标分流 | `frontend-experience-review`（作者自检 + 独立审查者 [Independent Code & UX Reviewer](conversation://f73e7a1d-992c-462f-b09f-1dad362a4cf6)，1280×840 实渲截图与图标资源审查） | `pass`（Windows 原生任务栏/WebView2 实机交互 `inconclusive`） | 1280×840 准备中、磁盘不足（`1.6 GB` vs `1.1 GB`）、目录权限受阻（`os error 5`）三态画面层级清晰、无重复说教或误导归因；macOS 保持单色模板 `tray.png`，Windows 改用高对比彩色 `128x128.png`。本机为 macOS arm64，Windows 10/11 任务栏缩放与 WebView2 前台焦点实机表现交远端 `Desktop client candidates / windows-x64` 验证。 |
| G1-3：最终契约归并一致性（`desktop-client.md`、`service-lifecycle.md`） | `change-code-review`（独立审查者 [Independent Code & UX Reviewer](conversation://f73e7a1d-992c-462f-b09f-1dad362a4cf6)，`corrected-delta`） | `pass`（`aligned`） | 两份 canonical spec 均从用户/运维者可观察行为表述，无内部符号泄漏，与 `5488d9ec1` 实现及测试保证严格一致，`./scripts/docs-check` 通过。 |

## Findings 与关闭

1. **F1（`apps/node/src/lifecycle.ts`，`high` / `CONFIRMED` → `closed`）**：
   - **问题**：首轮伴随文件位于 `<lock>.owner.json`，当进程因 `SIGINT`/`SIGTERM` 触发 `proper-lockfile` 的 `signal-exit` 仅删除 `lockDir` 而残留旧 `.owner.json`，或多个等待进程并发执行死锁回收时，存在误删新持锁进程的活伴随文件乃至活 `lockDir` 触发 `ECOMPROMISED` 的竞态；且同级 `.owner.json` 未在 `.gitignore` 中忽略。
   - **Resolution（`5488d9ec1`）**：将伴随身份与过渡守卫收敛至已被 `.gitignore` 忽略的 `.gateway-owner/` 下（`<lock>.json` 与 `<lock>.guard/`），守卫内使用进程专属标记 `owner-<pid>-<birthTag>.json` + 非递归 `rmdir` 实现无误伤互斥，串行完成 `signal-exit` 残留清理、死锁回收、`lockfile.lock` 获取及新伴随写入，并注册 `process.on("exit")` 同步清理；新增 4 路并发 + `1.4s` 心跳回归测试。
   - **独立关闭依据**：独立审查者于 `5488d9ec1` 复核 `withLockTransitionGuard`、`reapDeadGuardDir` 及并发回归测试，确认两条触发路径均已消除，判 `closed`。
2. **F2（`apps/desktop/src/lib.rs`，`high` / `CONFIRMED` → `closed`）**：
   - **问题**：首轮 `is_active_gateway_lifecycle_lock` 在 Rust 监督线程内直接无互斥重命名删除 `.gateway-lifecycle.lock`，与 `state.node_lifecycle` 之外的 `inspect`、`update-worker` 或运维 CLI 存在跨进程删锁竞态。
   - **Resolution（`5488d9ec1`）**：移除 Rust 侧一切锁目录写/删操作，将 `is_active_gateway_lifecycle_lock` 改为 100% 纯只读探测（同时礼让 5s 内活跃的 `.guard` 过渡窗口），识别死锁返回 `false` 后统一交由 Node `manageGateway` 在 `.guard` 保护下安全回收。
   - **独立关闭依据**：独立审查者于 `5488d9ec1` 核实 `lib.rs` 已无任何文件系统变更调用且与 `node-lifecycle.mjs` 协同通过，判 `closed`。
3. **F3（`apps/desktop/src/local_node.rs`，`low` / `CONFIRMED` → `closed`）**：
   - **问题**：首轮 `classify_seed_error` 子串匹配 `"os error 5"` / `"os error 32"` 缺少数字右边界且未区分 Windows 与 POSIX 同名 errno（如 Windows `os error 50` 或 macOS `EIO(5)`/`EPIPE(32)`）。
   - **Resolution（`5488d9ec1`）**：新增 `extract_os_error_code` 闭合非字母数字边界，并通过 `classify_seed_error_for_os(err, is_windows)` 严格区分 Windows（`112|39`、`5|32|33`）与 Unix（`28|69|122`、`13|1`），补充 `seed_tests.rs` 边界断言。
   - **独立关闭依据**：独立审查者于 `5488d9ec1` 核实实现与测试覆盖，判 `closed`。

当前存活 findings：无（0 项）。

## 流程收口

- 重要目标和关键设计覆盖：Issue B / C / D / E / F 全部修复并由单元与跨进程集成测试覆盖，既有 `bugfix-807` / `810` / `812` 不变量完整保留。
- 开放问题 / pending / inconclusive：本地无未决阻塞项；Windows x64 原生安装包与任务栏/WebView2 表现由 PR 远端 `Desktop client candidates` 工作流承接。
- 最终 delta 校对：`aligned`（`docs/specs/im/desktop-client.md`、`docs/specs/gateway/service-lifecycle.md`）。
- 版本变化后保留 / 补验的判断与依据：`ad8d5b299` 之后仅修改 `apps/desktop/build.rs`（为 Windows MSVC 测试与正式目标统一嵌入 `Common-Controls 6.0.0.0` 清单，消除 `--lib` 测试 `0xc0000139`）、`lib.rs` / `autostart.rs` 的 `#[cfg]` 告警门控，以及 `apps/desktop/tests/node-lifecycle.mjs` 中跨死锁崩溃恢复断言的观察时序（在杀掉旧网关前写入死锁模拟文件，并在 `waitFor` 内等待恢复后的 `manageGateway` `finally` 释放锁目录），未改变运行时逻辑或外部契约，且已通过本地测试与独立 `patch` 复核（`pass`）。
- 测试资源回收结果 / 例外保留项、owner 与回收触发：所有临时测试子进程与临时目录均已在测试内回收，本地 `apps/desktop/target` 编译产物已通过 `cargo clean` 清理以释放共享磁盘空间；当前开发 worktree（`/Users/czj/.t3/worktrees/nano-multiagent/unit-bugfix-819-desktop-e09bd061465827a5`）按仓库规范保留供 PR 审查，待 PR 合入 `develop` 后触发清理。
- 交付范围与剩余事项：归档 `bugfix-819-desktop-windows-host-resilience` 后推送分支并向 `develop` 创建 PR，跟进远端必需检查（不自动 merge）。
