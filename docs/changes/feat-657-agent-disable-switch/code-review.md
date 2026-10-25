# Code Review — feat-657

## Round 1

- review_mode: full
- executed_base: `797b225df`
- validated_at: `935510058d338866e2310f54c1804d6120eac51c`
- reviewer: independent static reviewer; 未参与实现。
- 范围：完整 implementation diff、真实调用方、M1/spec/design 与全部四份 delta；不修改源码、测试、配置或设计。共享现场原始状态 clean。
- 结论：2 个 P2 CONFIRMED；修复前不通过。没有将进行中的产品验收、最终 CI 或 spec 归并计作缺代码。

```json
[
  {
    "file": "packages/dsh-integration/src/runtime-migration.ts",
    "line": 233,
    "summary": "[P2] 在只读副本上读取源 domain，避免 plan 自动改写源快照",
    "failure_scenario": "源目录含锁定公开存储适配器可读取的 legacy 单文件 domain（独立复现使用公开 modelDomain 的 single layout 写 nano_model.json）时，plan 的 storage.domain.open(spec) 会触发 JsonStorageBackend 的 per-record bootstrap，在源 storages 下新增 nano_model/。同一次 plan 随后误报 Source changed while planning，要求操作者停止实际上已停止的 writers。源快照已被规划操作修改，违反迁移保留静止源的约定。应在保护的临时副本读取 domain，源摘要和源目录保持原样，并用同一公开 API fixture 保护该行为。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/node/src/agent-lifecycle.ts",
    "line": 88,
    "summary": "[P2] 将停止失败的具体原因传到 lifecycle 状态",
    "failure_scenario": "受管 owner cleanup 抛错，或 DSH event loop 卡住达到停止截止时，RuntimeSupervisor 仅把原因写 onError，返回 confirmed=false；Node 只发布 managed_cleanup_unconfirmed 且不发送 error_detail。IM report 将 error_detail 写成 null，Web/iOS 都只能展示通用重试说明。用户无法区分超时与清理异常，未兑现 spec 清理超时或失败场景要求的具体原因。应保留有界、安全的停止原因并发布给 owner；非 owner 已有诊断脱敏继续适用。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 直接证据

第一项在临时副本执行下列命令独立复现，执行后删除临时目录；没有运行 live migration 源。公开 adapter 的 legacy bootstrap 机制另由已锁定 `dsh-storage-json/lib/index.js` 的 `loadPerRecordState/bootstrapLegacyUnit` 核实，无 private import。

```sh
PATH=/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin:$PATH node --input-type=module <<'JS'
import {mkdtemp,rm,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {openMigrationStorage,planRuntimeMigration} from './packages/dsh-integration/lib/runtime-migration.js';
import {modelDomain} from './packages/dsh-integration/lib/model-policy.js';
const home=await mkdtemp(join(tmpdir(),'nano-review-migration-'));
try {
  const db=new DatabaseSync(join(home,'node.sqlite3'));
  db.exec("CREATE TABLE node_owner(owner_id TEXT); INSERT INTO node_owner VALUES('owner'); CREATE TABLE sessions(session_id TEXT,agent_id TEXT,binding TEXT)");
  db.prepare('INSERT INTO sessions VALUES(?,?,?)').run('s','a',JSON.stringify({sessionId:'s',agentId:'a',ownerId:'owner'}));db.close();
  const storage=await openMigrationStorage(home);
  const domain=await storage.domain.open({...modelDomain,layout:'single'});
  await domain.table('sessions').put(Buffer.from('s').toString('base64url'),{revision:'1'});
  await domain.close();await storage.close();
  console.log('BEFORE',await readdir(join(home,'storages')));
  const plan=await planRuntimeMigration({home,nodeId:'n',ownerId:'owner',agents:[{agentId:'a'}],stopped:true});
  console.log('BLOCKERS',plan.blockers);
  console.log('AFTER',await readdir(join(home,'storages')));
} finally {await rm(home,{recursive:true,force:true});}
JS
```

实际输出：`BEFORE ['nano_model.json']`；`BLOCKERS ['Source changed while planning; stop all writers and take a new snapshot']`；`AFTER ['nano_model','nano_model.json']`。

第二项直接调用链：`client.ts:191-204` 的 deadline/catch → `NodeAgentLifecycle.stop:82-89` → `publish:91-97` → IM `AgentLifecycles.report:125`；客户端仅在 `error_detail` 非空时显示原因（Web `agent-lifecycle.tsx`、iOS `AgentLifecycleView.swift`）。已有真实进程测试证明清理异常和 event-loop 卡住是可达到场景，当前只断言 confirmed=false，没有保护可见原因。

## 已覆盖与反证

- Lifecycle CAS/幂等、当前连接/revision/process 身份、停用先关准入、Task 跨 await 再校验、旧审批和旧输出拒绝；没有发现绕过。
- 进程隔离、公开 DSH owner/loop/subprocess teardown、所有 native Agent 清理但仅 bound roots 投入 Work、冷 inbox/owner fence、Schedule future-only、外部 channel 原代次、最终 Work/ACK 与冷原生历史路径已核查。
- 在线新建 Agent 的初始 lifecycle 候选已反证：`control.ts:476` 在事务提交后主动 deliver，因此未列 finding。
- 未要求超出用户接受的 DSH macOS 受管边界的 OS containment；未将进程组 fallback 当成应新建隔离器的缺陷。
- 复用 caller 的版本化 build/typecheck、PA/IM/Node/native/cold-history 测试证据；读取 `/tmp/nano-feat657-build3.log`、`/tmp/nano-feat657-typecheck3.log`、`/tmp/nano-feat657-stop-fix-test.log` 的通过结果。未重复全量测试。

报告由共享现场 caller 提交；本 reviewer 未提交、未创建额外 worktree 或服务。
