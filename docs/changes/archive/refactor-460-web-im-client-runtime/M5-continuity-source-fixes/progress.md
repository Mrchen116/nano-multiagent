# refactor-460-M5 — Progress

## 启动与根因

- 2026-07-13：orchestrator 根据 Round 3 verifier 与独立 code review 追加 M5；用户要求真问题由 orchestrator 亲自修改，不再委派 impl worker。
- systematic-debugging 红测确认七项行为缺口与一项架构重复 owner：server 实际 wire ids 为 `[1..501, 501]`；Gateway 新泡继承旧泡 visibility；runtime cold/resync/recovery/validation 四项失败；external 实际事件序列不提示；toast/notifier 重复拥有 accumulator。
- C1 红测：`d963e2a3`，4 个文件、155 行；各缺口均在修复前稳定失败。

## R1 — replay/live 稳定边界

- Status: DONE
- Decision: replay/register 与 live 继续共用 per-user handoff；handoff 内固定 event-store cutoff，分页只读 cutoff 内快照。每条连接以 `delivered_through` 记录 replay/live high-water，解析 canonical wire event id 后跳过已覆盖广播。
- Rationale: 锁只能防 overtaking，不能区分“等待锁的广播是否已被 replay 覆盖”；high-water 才是两条路径的 exactly-once 交界。
- Evidence: user-stream + repository focused 14 passed；优化测试 stub 后 user-stream 9 tests 在 0.22s 内通过。

## R2 — browser continuity 与 canonical trust boundary

- Status: DONE
- Decision: cold baseline open 后 recovery；resync success 才完成 generation，failure 关闭并退避；recovery 只按 in-flight promise 合并。已知 Chat canonical schema 移到 user-stream runtime，在 cursor/fan-out 前验证，Chat mapper 复用。
- Rationale: cursor 是共享副作用边界；任何 domain subscriber 才发现坏帧都已经太晚。generation 不是“一生只恢复一次”的业务边界。
- Evidence: runtime/reducer focused 42 passed；包含 failed sync 后新 generation 把 cursor 50 降到 3，并接收 event 4。

## R3 — delivery/notification ownership

- Status: DONE
- Decision: steer roll 后清空 bubble-local visibility/discard；external shadow 使用 Conversation REST 已有 `external_source` 区分 owner 代存与 self-authored，不加协议字段；toast hook 唯一拥有 completion accumulator，desktop notifier 只消费 candidate。
- Rationale: run context 与 bubble context 生命周期不同；external sender 的持久化 owner id 不是交互语义；同一 sessionStorage 状态不能由两个 React consumer 各自归约写回。
- Evidence: Gateway lifecycle 35 passed；notification/App focused 27 passed；frontend focused 65 passed；production build passed；首次 frontend full 64 files / 588 tests passed。

## R4 — validation closure

- Status: DONE
- Browser finding: 首版 external 修复依赖 conversations 已在 React Query cache。新 external conversation 与首条 `message.created` 连续到达时，消息会先于会话身份进入缓存，因持久化 owner id 等于当前账号而被误判 self-authored。新增红测后，协调器只在该歧义窗口通过既有 `listConversations` 拉取权威身份，再决定 toast / local unread；不增加 wire 或 REST 字段。
- Browser evidence: 仅在 Codex 内置隔离浏览器中验收。真 IM + Gateway + Vite 下创建新 external conversation 后，首条消息显示 sender `Visible External Sender`、preview `VISIBLE_TOAST_M5` 的 toast，并在侧栏显示 `1 unread`；恢复 4 秒 dismiss、移除 instrumentation 后重新加载，应用正常且无调试 dataset。未使用 Chrome、Computer Use 或 macOS System Settings。
- Automated evidence: focused Python 66 passed / 1 skipped；ruff `src tests` passed；backend `pytest -m "not e2e" -q` 3513 passed / 1 skipped / 23 deselected；e2e-critical 非 slow + 240s case timeout 15 passed / 2 deselected；最终 frontend full 64 files / 589 tests passed；production build 与 `git diff --check` passed。
- Infrastructure note: e2e 脚本内个别 case 自设 120/180 秒等待，但项目全局 pytest timeout 为 90 秒；heartbeat slow case 另有严格 xfail #126。因此验收使用 `-m "not slow" --timeout=240`，保留真实 Gateway/IM 栈而不把基础设施 timeout 误判为产品失败。
- Next: 并入 unit 分支，执行独立只读 verifier / code review / product review；任何确认问题由 orchestrator 本人修改。

## Commits

- C1 red tests: `d963e2a3`
- C2 source fix: `22321a76`
- Browser race fix: `f982d496`
- C3 evidence/docs: this documentation commit
