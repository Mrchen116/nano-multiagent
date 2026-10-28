# 实施验证

基线：origin/main ff326c351；初始设计 2bca4754e。隔离 worktree，无生产写入。实现后的 commit 与最终门禁见后续记录。

## 测试归属与处置

- 扩展 `packages/dsh-integration/tests/knowledge.test.ts`：新旧统计隔离、75 次调用、样本被其他 Agent 挤出、重开文件、去重与跨 30 天窗口；扩展既有 Global Inbox 真实 runtime 测试，确认 skill_creation=false 仍计数且重启不重计。F4 原维护测试保留，仅更新内部签名。
- 扩展 `apps/im-server/tests/agent-settings.test.ts`：两条公开 API 共用投影，不透出内部聚合，旧 live/snapshot 拒绝与新版离线缓存保留。
- 扩展 Web 现有 Agent 页测试：累计与窗口合计分开、服务端固定 UTC 日期、起点前未知桶；未新建重复 E2E 套件。
- 扩展 iOS AgentContractsTests：解码后的累计/窗口值及图表日期过滤；无导航或系统集成改变。

## 已执行

- Red：新增存储回归在旧实现失败，期望新计数 0、起点 null、无新引用，实际返回旧 999 及旧引用。
- Green：knowledge.test + knowledge-review.test，10 tests 通过；包括 F4、维护 fork 与关闭自进化的真实 DSH 子进程。
- IM settings：20 tests 通过；Web Agent 页：27 tests 通过。
- pnpm build/typecheck/check:ios-runtime、Web production build 通过，使用 Node 24.22.1。前端构建仅有既有 bundle 体积提示。
- iOS 新统计契约测试通过；首次全量测试在旧通用模拟器的图片剪贴板用例失败，尚待隔离基线复核，不据此声称全量通过。

## 设计澄清

`/skills/usage` 真实现有离线契约是 HTTP 503（rpc helper），不是设计分析中误写的 node_online:false。实现保留 503；设置页沿用 unavailable/last_known 语义。此为 current grounding 文字纠正，无新增兼容分支。

原型截图为 gitignored 本地产物：unit 根部 `evidence/prototype-{desktop,mobile,mobile-scrolled}.png`，不提交 Git；设计中含实际观察文字，交付 PR 不将图片链接当作远端证据。

## 扩大验证（2026-10-28）

- 固定实现 `28b205259`。首次不限制并发的 backend/Web 全量在多个无改动区域发生超时；降低本任务并发后重新运行，未改超时阈值或产品代码。
- `pnpm test --maxWorkers=2`：143 files / 774 tests，其中 142 files / 773 tests 通过，唯一失败为现有 agent-disable-native 的 PTY cleanup；随后以 `pnpm exec vitest run packages/dsh-integration/tests/agent-disable-native.test.ts apps/im-server/tests/e2e/control-work.test.ts --maxWorkers=1` 单独复验，2 files / 11 tests 全过。PTY 失败未稳定复现，不能断言已定位根因；本次统计修复不改终端生命周期。
- 全量发现既有 control-work E2E 的 Skill usage fixture 仍是旧 envelope；补齐新起点/窗口和引用字段，不放宽断言；上述 11 tests 包含该公开跨进程入口通过结果。
- `pytest -m "not e2e" -q`：100 passed / 28 deselected；`ruff check .` 与 `ruff format --check .` 通过。
- iOS 专用模拟器完整 `build.sh test` 通过（`/tmp/skill674-ios-isolated.log`）；`build.sh archive` 通过（`/tmp/skill674-ios-archive.log`）。旧通用模拟器剪贴板失败未在专用模拟器重现；不修改该无关测试。
- final sync 检查：2026-10-28 fetch 后 origin/main 仍为 `ff326c351d104447028f4b185740ab6d6be55de6`，无 main 增量。已审代码未变化，仅 E2E fixture 与运行证据补齐，待独立审查者核对增量。

- Web `npm test -- --maxWorkers=2`：108 files / 1029 tests 全通过；`npm audit --audit-level=critical` 退出 0（0 critical，现有 11 项非 critical，无依赖变更）。所有适用本地测试文件已获得通过结果；首轮资源并发失败及 PTY 复验保留如上。

## 最终集成与门禁

- `origin/main` 在最终收尾推进至 `b8fc5edefcb74ec8a8888aeb7fa245779e644253`，合并树 `6a16e72d2009adea95f1f1624a13dbf74d9a67fa`。独立静态审查核对主干序列化和 TaskGraph 增量：usage/knowledge/Web/iOS无改变，control共享模块需局部验证；其余门禁保留，详见 unit verification。
- 合并后 `pnpm build && pnpm typecheck` 通过；IM settings/control-work/control 与 serialization 共4 files / 47 tests通过；架构contract 13 tests通过。日志分别为 `/tmp/skill674-sync-build.log`、`/tmp/skill674-sync-tests.log`、`/tmp/skill674-sync-contract.log`。
- 独立产品验收 pass，真实UI关闭自进化并调用本地确定性 provider：累计75→76、30天1→2，旧记录0/暂无新调用，桌面/390px/空态对照通过。完整观察与截图位置见 unit review。
- 独立 code review findings=[]、full verification=pass、corrected delta=aligned。canonical只归并已核对的同一delta文字；归档与证据提交不改运行代码，门禁 retained through 最终交付提交。
- `e2e-down.sh` 已完成；本任务本地 provider已停止，53171/60675均无监听；专用iOS模拟器已删除，构建和测试日志保留于 `/tmp/nano-ios-skill674`。开发worktree保留待PR审查。
