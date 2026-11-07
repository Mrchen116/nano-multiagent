# feat-716 — 恢复实施记录

## 版本与范围

- 当前集成基线：`origin/develop` `eeaea47921806936da20e78c9ed96167716f5037`，PR 目标 `develop`。旧 `unit/feat-716` `6e42f0fd8` 与全部 dirty 留在 `.worktrees/feat-715-integrated-bg`，额外备份 `/tmp/feat716-recovery.rXzQ9G`。新专属树 `.worktrees/feat-716`，分支 `codex/feat-716`，三方干净应用本 unit 已有提交差异和 Web WIP；没有 reset 或改主树用户 dirty。
- 范围以原 spec + 人类恢复决定为准：只修重复注入；Work/原生轨迹实际模型输入的可见性是正确行为，不做任何呈现修改。
- 旧 Gate 2 的目标与大体边界仍适用；已按负责人确认纠正最新卡失效后旧卡复活的 SQL 设计（见 design Changelog）。不得把历史 M1 证据或自检直接当当前独立实施门禁。

## 实施与测试策略

- M1 server 派生与 CAS/幂等底座迁入当前 develop；两端删除客户端选最近三张卡的权力。服务端自然消息与附件快照决定幂等身份，既有请求冻结背景由中心保存，旧指纹按共同字段比较。
- Web 继续保存真实改动；发送前 flush、冲突三列比较与显式采用、切会话串行清除及迟到自有保存补清除。复用既有 `im-message-attempts` IndexedDB，v2 仅追加 `watermarks` store，不新建独立数据库或迁移/改写旧 attempts；按 origin + account 隔离、单调 max、128 条上限，logout/revocation fencing。
- iOS 由独立实施执行者 `576bfcf4-453d-49c5-8ef8-f1fe431232cd` 负责同一 worktree 的 `src/IM/ios/**`，只改该范围，主执行者集成提交。两端改动不涉及 Work 展示。
- 既有行为保护的处置：Web `message-pane*`、`interactive-flow`、`interactive-card`、`chat-api`、`send-attempt-store` 重写旧 contexts 参数断言，保留真实私聊保存/群聊隔离/冻结请求/账号隔离等风险；删除卡片局部“直接载入最新”的绕过行为，冲突恢复集中到 composer 的只读比较→警示采用。`interaction-background.test.ts` 保护 coordinator 的持久化/清除链；`draft-failure-notice.test.tsx` 从真实卡片和 composer 接线保护失败恢复，不与 server pending SQL 重复。

## 有意义的失败复现与修复

以下为本次当前集成树新增红测，不冒称旧 M1 曾遵循 red-first：

1. Web 采用远端草稿 GET 失败：旧 `load()` 吞异常，采用句柄仍清冲突，发送按钮错误恢复。`draft-failure-notice.test.tsx` 的 `keeps the conflict and local edit when fetching the draft to adopt fails` 修复前实际失败（send 未 disabled）；修复后通过，保留本机编辑、正文和会话拦截，读取失败可再试。
2. Web 发送等待卡片保存期间输入新正文：旧实现 await 后取 live snapshot，旧发送成功把新正文清空。`message-pane-composer-draft.test.tsx` 的 `does not clear text edited while the submitted message waits for its card save` 修复前实际收到空值；修复后通过，await 前冻结正文/附件/composer revision。
3. 水位账号切换两条 race：`does not persist a save under an account selected while IndexedDB is opening`（错误写入 u2）与 `ignores a previous account discard completion instead of deleting this account watermark`（错误删除 u2）。修复前二者均红；修复后 coordinator tests 通过，持久化捕获 account/session、事务完成才 resolve，晚到旧 session 不改变新账号。
4. 服务端日期：`normalizes ISO offsets before comparing and ignores non-ISO date strings` 修复前非 ISO `11/05/2026` 被接受；修复改严格 ISO + canonical UTC 再比较，窄测试通过。
5. 唯一替换：`does not resurrect the earlier card when the latest edit becomes read-only or superseded` 修复前返回旧 A 非 null；负责人确认按原目标纠正设计与候选 SQL，最新失效直接 null，不回退旧卡。关联显式提交消耗另卡但不重复注入的测试保留通过。
6. iOS composer conflict 新测试先跑真实 Xcode 红（exit65，发送 POST 被错误发出、PUT0、正文清空/error nil），详见本地 `/tmp/feat716-ios-red.log`；执行者后续报告 18 项窄测试通过，主执行者尚待最终证据与集成核验。

## 已观察验证与限制

- 本机：`python3 scripts/dev_host.py check` 成功，Air、Node24.22.1、pnpm11.7.0；`pnpm install --frozen-lockfile`、contracts build、frontend npm ci 成功。依赖 audit 现有11项风险，无额外升级。
- Web 窄测试中的 coordinator19、composer18、send-attempt3、interactive-card14 已绿；composer conflict5/interactive-flow7 最后发现用呈现 prop `isDirectChat` 代替会话 type 会把测试中的 direct 当 group，现已改为显式 conversation type 透传，串行复验12项通过；`npx tsc -b` 通过。随后 `npm exec -- vitest run --maxWorkers=1` 前端全套 115 files / 1110 tests 全绿（202.93s，exit0，`/tmp/feat716-web-tests.log`）。
- 服务端新增唯一替换测试红后已修；`pnpm exec vitest run --maxWorkers=1 apps/im-server/tests/interactive-background.test.ts apps/im-server/tests/interactive-messages.test.ts apps/im-server/tests/message-attempts.test.ts`：42项通过，exit0。
- 共享主机存在其他任务；所有后续重测试低并发，Xcode `-jobs 2 -parallel-testing-enabled NO`，Vitest `--maxWorkers=1`。不停止其他任务进程。
- 当前未起真实 daily 栈、未观察当前实际 provider 输入、未做真实 UI 旅程、未做当前独立代码/Context/体验门禁、未归并 canonical/归档/PR。旧原型画面不可当当前实现截图。
- 独立门禁配置阻塞：可用 native subagent 接口没有 `model`/`reasoning_effort` 参数，不能显式选择当前适配表要求的固定审查模型。已向主 PA 报告，其明确：继承 + 记录差异不能等价门禁，不自审或造 CLI 替代协议；冻结时交事实包和具体配置缺口，由主 PA 处理所需的人类决定。
