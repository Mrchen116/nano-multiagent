# Code Review: feat-637

## Round R1

- review_mode: full
- diff_range: `5462b7217421a2c27871c1c5951c1e48644e54ba...d617906aed41fa14a34f4b3f1b5e49f179ed4129`
- validated_at: `d617906aed41fa14a34f4b3f1b5e49f179ed4129`
- executed_base: `5462b7217421a2c27871c1c5951c1e48644e54ba`
- 独立审查；未修改实现、测试或设计，未新建 worktree，未提交。
- 覆盖：完整 unit diff、实际调用方、current Gateway/IM 契约、spec/design/delta/milestone，以及有效测试日志。产品质量与视觉验收由独立产品 reviewer 负责。

```json
[
  {
    "file": "packages/dsh-integration/src/knowledge/runtime.ts",
    "line": 297,
    "summary": "[P2] 仅在原生 completed 时转换 Memory 读取未完成终态",
    "failure_scenario": "Memory 或 combined review 已尝试读取一份 Memory，但另一份尚未读完，随后 fork 因现有 16 步限制被取消。work.controller.signal 并未因此 aborted，当前分支无条件以 incomplete 覆盖 result.stopReason，将原生 aborted/cancelled 记为 error/memory_read_incomplete；provider 失败也会丢失原 diagnostic。design.md:162-163 明确仅正常结束且读取不全才转换，原生失败或取消须保留。独立真实 DSH 复现 /tmp/feat637-static-step-limit.mjs 的轨迹返回 state=cancelled、stopReason=aborted，knowledge.facts 却返回 status=error、diagnostic=memory_read_incomplete；/tmp/feat637-static-step-limit.log 为成功输出。provider 失败对应 /tmp/feat637-static-native.mjs 和 .log。将读取转换限定在 result.stopReason === 'completed'，其余终态与 diagnostic 保留，并在已有生命周期测试中保护该分支。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

复用的有效验证：`/tmp/feat637-tests-serial.log`（122 文件/581 项）、`/tmp/feat637-last-tests.log`（最终两文件9项）、`/tmp/feat637-focused.log`（6文件22项）、前端103文件963项、build/typecheck/Python65通过日志。未机械重跑全量。首次并行 ENOSPC 失败记录仍保留，不据此否定后续串行通过结果。新增临时复现只使用合成资料，已 shutdown 并删除各自运行目录；脚本和脱敏输出保留在 `/tmp`。

## Round R2

- review_mode: patch + finding closure
- diff_range / fix_delta_range: `d617906aed41fa14a34f4b3f1b5e49f179ed4129..fc101f8532e638324ebcf8bf60e51044af68c377`
- finding_origin_head: `d617906aed41fa14a34f4b3f1b5e49f179ed4129`
- validated_at: `fc101f8532e638324ebcf8bf60e51044af68c377`
- executed_base: `5462b7217421a2c27871c1c5951c1e48644e54ba`
- 开始时 clean，HEAD 与冻结版本一致。只追加两份报告，不修改实现、测试、设计或 runtime，不新建 worktree，不提交。

当前 patch 的存活代码 finding：

```json
[]
```

### Finding closure

| 原 finding | 结果 | 直接证据 |
|---|---|---|
| R1 P2 / verifier R1-W1：读取未完成覆盖原生终态 | closed | `runtime.ts:290` 仅对 `result.stopReason === 'completed'` 计算 incomplete，原 provider/aborted 进入原结果分支。`knowledge-policy.test.ts:67-108` 用真实 DSH 分别触发 provider failure、16步取消，核对持久 review 与 trajectory 的原终态和下次周期重试。红测 `/tmp/feat637-review-red.log` 精确复现两项失败；当前两文件9项通过 `/tmp/feat637-review-fixes.log`。不要求宿主凭空补全 DSH 没有返回的诊断。 |
| verifier R1-W2：关键回归缺口 | closed，详见 verification R2 | 新增同根独立周期及联合在途关闭；扩展 F4 两会话 fixture 的运行中排除、错误 owner/缺失历史排除、并发、新使用保留、已处理历史再到期；文件层覆盖错 target/root、非 patch、接受后来源改手工。无需为每个等价拒绝字段复制套件。 |

### 新增 patch 核对

- Memory 单项／combined／前台 Memory 说明排除临时任务状态、待审批与延后 Skill 修改队列；Skill/combined 中的 current situation/state of operations 改为 durable environment facts。与既有无临时进度、单一归属和用户约束一致；prompt-map 明确这是必要适配，未增加协议、审批器或分类引擎。真实模型修复效果仍由产品 reviewer 核验。
- `runtime.ts:327` 只新增排除自动 `skill-catalog`，与已排除 runtime-context/system 同层；真实 user/message、skill-invocation、call/result 和完成边界保留。两个不同合格 session、20,000/100,000 上限、来源和目标检查未变化。24个真实发现 Skill 的 fixture 确认目录本身超20k，旧代码无法启动，当前代码启动同一目标 F4，且仍排除未完成和已处理历史。红测 `/tmp/feat637-catalog-red.log` 与最终通过日志支持该修复。
- 设计文档的刷新措辞、引用和 runbook 校正没有改变公共行为或 milestone；spec 与两份 delta 相对 R1 未变。本轮未扩大到原分支 full 审查，R1 未变化范围保留。

结论：patch 审查通过，R1 finding closed；0 存活代码问题。复用现有窄测试和相关 build 证据，未重跑全量。不代替独立产品21场景验收或最终同步后的失效判断。

## Round R3

- review_mode: bounded patch
- diff_range: `138eccfd7..1bc6219356186ebc0a3f255cf4a441936495d8e3`
- validated_at: `1bc6219356186ebc0a3f255cf4a441936495d8e3`
- executed_base: `5462b7217421a2c27871c1c5951c1e48644e54ba`
- 先前静态版本：`fc101f8532e638324ebcf8bf60e51044af68c377`；至 `138eccfd7` 没有产品代码、spec 或 delta 增量，R2 未变范围 retained。

```json
[]
```

实际改动仅两处前台模型指引及对应设计／来源／进度记录：Memory 工具描述要求写前完整读取当前双文件、保持项目身份、不用陈旧快照重复保存、尊重延后维护；Skill system section 同步明确回复消息不把后续同执行调用变为后台 review。`KnowledgeFiles` 实际路径为 `<workspace>/.nanoassistant/memory/{USER,MEMORY}.md`，描述与落点一致。未修改 schema、执行器、硬检查、后台调度或冻结快照，不产生新的权限或事务承诺。文档明确这些是操作指引，未将其写成宿主强制保证。

复用 `/tmp/feat637-r3-tests.log`：最终两文件9项通过；`/tmp/feat637-r3-build.log`：package tsc 构建成功。它们保护既有执行机制，不证明模型会服从新说明。真实 Global 输入 `96db63dddaec4425bbc0bcfcf3fe2c09` 的产品失败由 acceptance 保留，修复效果待产品 reviewer 同条件复验；本轮不关闭该产品 finding。

结论：当前 bounded patch 无可确认代码缺陷；R1 finding 保持 closed。未运行全量、未修改实现/测试、未提交，保留并行 acceptance.md。

同轮收尾纳入 caller 新冻结 `1bc6219356186ebc0a3f255cf4a441936495d8e3` 的补充：仅 read 明确不存在才按空文件处理，拒绝／其他失败／不完整才跳过。该句与后台原有缺失文件规则和实际首次保存路径一致，避免将新 workspace 的无文件误判为不可维护。设计和 prompt-map 同步，无新执行逻辑。上述 R3 validated_at/diff_range 已延伸至此版本；两文件9项与 build 的实际运行版本为前一个 `ff30a6ea8`，最后增量仅此模型说明，机制回归 retained，不冒称在最后 SHA 重跑。
