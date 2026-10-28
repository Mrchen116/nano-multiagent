# refactor-671: 序列化职责与字节契约 — 技术方案

对齐 motivation.md；Full，单 M1，零用户面。

## Changelog

## 现状分析

### 涉及范围

基线 a34af8473。实际全仓符号搜索（含源码/测试）得到下表；这里记录的是基线事实，不将未证明的跨端差异修成新契约。

| 实现 | 字节和输入语义 | 真实消费者及持久影响 | 处理 |
|---|---|---|---|
| IM task-graphs canonicalJson | JSON.stringify replacer 递归排序，UTF-16 码元排序，保留非 ASCII；数组保序，数字索引仍按 JS 枚举；toJSON 先于 replacer | Task wait/identity 比较、mutation 请求摘要，迁移摘要/完整性比较；Channels config/runtime/信封存储、AAD 和 secret 明文 | 原样搬至 product-contracts/serialization 的 sortedJsonUtf8，逐个更新调用者 |
| product-contracts configuration canonicalJson | 递归预遍历排序，然后 stringify；转义 U+0080..FFFF（含成对代理码元），U+007F 原样；不等同于 replacer 的 toJSON 行为 | 配置 fingerprint/heartbeat；根入口显式导出覆盖 interactive 星号导出；IM 消息 attempt/交互 publication/state/semantic、gateway 比较；PA Inbox/发送 publication 幂等身份 | 原样搬为 sortedJsonAscii，调用点使用显式名称和独立 subpath |
| IM control asciiJson | Task replacer 输出再转义 U+007F..FFFF | gatewayCandidate heartbeat 和持久 candidateFingerprint；既有 DEL 差异不修复 | 本地 serializeCandidateJson 使用 sortedJsonUtf8 后按原正则转义，保留领域策略 |
| IM identity canonical | 预遍历排序并转义 U+007F..FFFF | members/snapshot 持久 JSON、迁移确认比较、device-binding AAD/证明 | 本地 serializeIdentityJson 使用 sortedJsonAscii 后仅补转义 DEL，保留领域命名与 export 测试入口 |
| Channels channel-credentials canonical | 只排序顶层，UTF-8 Buffer；不递归 | ChannelKey seal/open 的 flat ChannelAad（字符串和 revision 数字）与 string secret record；openBinding 顶层 AAD（purpose/node/operation/epoch/expires） | 私有 encodeCredentialRecord 命名，保留浅排序原实现，不将额外嵌套字段的字节偷偷改成递归 |
| Node device-binding canonical | 顶层排序并转义 U+007F..FFFF | 设备绑定 confirmation 的 HMAC；confirmation 是来自中心的 JSON | 本地 serializeBindingConfirmation，仅改名；不合并浅/深排序 |
| integration workflow/control canonical | 与 Task 相同的 replacer + UTF-16 排序，不转义；输入为前序 key、prompt、去除 label/phase 的 options（含嵌套 schema） | WorkflowControl.call → SHA-256 → WorkflowCall.key 持久记录 → perform 重放完成前缀；由 workflow/service 装配 | 复用 sortedJsonUtf8，补固定历史调用 key 的 replay 测试，保持 options/持久化与执行时序不变 |
| product-contracts interactive canonicalJson | replacer + localeCompare，不转义 | 无直接消费者，根入口被 configuration 显式导出遮蔽；全仓无该文件函数的直接导入 | 删除这份无消费者的实现，避免根入口切换时误选 |

实际输入主要是 HTTP/WS 解析对象、SQLite JSON/row、配置投影、JSON 工具参数和 flat credential record。undefined 属性、null、数组、数字索引键遵循既有 JS 行为；函数不宣称 RFC 8785/Python 全域一致。对 Date/toJSON 等非 JSON 对象不新增支持或验证，搬移仍保留原 traversal，避免 unknown 类型入口暗中变义。

### 既有约束

SPEC 的 IM/Channels 只依赖 product-contracts；加密仍由 IM/Channels/Node owner 持有。独立 worktree、codex/ 分支；不改 Row/ImContext，不改原报告。跨包只用声明的公开 export。当前契约：docs/specs/im/agents-nodes.md 的节点/配置/渠道安全持久化、docs/specs/gateway/external-channels.md 的密文缓存与离线恢复、docs/specs/im/task-graphs.md 的持久任务；均无行为增量。

### 可复用能力

复用现有两种通用递归编码的完整实现，归入无 node:crypto 依赖的 serialization.ts 与公开 subpath。拒绝单个 options serializer：遍历顺序、转义边界、浅/深排序有真实差异，选项会隐藏误用。局部 owner 保留自身特殊规则，比增加五个跨包公共策略更小。所有现有 canonicalJson 仓内调用改为显式新名；包为 private，未声明的源码路径不保留兼容别名。

### 相关历史

configuration 的 approval_mode 兼容注释和既有 pre-strategy receipt 测试要求保留 null mode 的旧摘要；Task 协作迁移保留历史摘要；渠道密文缓存依赖 version 1 信封。对应历史不在本 unit 重做迁移。研究报告第 4 项是本次输入；第 1/2/3/5 项不实施。

## 架构总览

Task / Channels(IM) / WorkflowControl → product-contracts/serialization.sortedJsonUtf8。
配置 / IM 与 PA 幂等键 → product-contracts/serialization.sortedJsonAscii。
control / identity 在领域 owner 保留 DEL 特例；Channels 与 Node 在原 owner 保留浅排序编码。纯序列化不再依附 Task、配置、交互领域。

## 关键决策

- **以字节兼容为优先，不统一现有差异。** 保留 DEL、toJSON、浅排序的区别；shared 函数注释写清边界，不称其为标准 canonical JSON。
- **仅暴露两个无选项的纯函数。** 新 subpath 可独立消费；root 不再导出模糊 canonicalJson。直接导入明确语义，不保留无人需要的旧名别名。
- **不修改加密和配置归一化。** key derivation、salt/nonce、AAD 字段、版本、hash 输入投影保持原样。实际 ChannelAad/secret 是 flat，不证明嵌套扩展可跨 owner 互操作。
- **零用户面验证。** 对模型可见内容/选择/注入/恢复时序无改变；PA/Workflow 修改仅为同一字节函数的 import/name，既有幂等测试确认语义不变，因此无需完整 Context Review 或真模型测试。

## 接口与数据流

`@nano/product-contracts/serialization` 导出 `sortedJsonUtf8(value: unknown): string` 与 `sortedJsonAscii(value: unknown): string`。前者保持 native JSON replacer 行为，后者保持预遍历及非 ASCII 转义（DEL 不转义）。仅给 JSON 可序列化输入提供 string 保证；循环/BigInt/顶层 undefined 不扩展容错或 fallback。

密文路径保持：IM secret/AAD → sortedJsonUtf8 → IM X25519/HKDF/GCM → envelope → ChannelKey.open → 私有浅排序 UTF-8 AAD → 原明文。密钥与加密均不进入 contracts。

## 契约层增量 (delta-spec)

no spec delta。保持 SPEC 的现有包职责与依赖方向，不新增长期文档；公共函数的精确兼容说明留在代码 API 注释，不复制到多个规范。runtime dependency contract 的显式允许列表仅为实际使用者补 serialization subpath，保留所有原有依赖方向限制。

## 验证与测试取舍

1. 搬移前采集固定向量：嵌套对象/数组、中文、emoji、U+007F/U+0080/U+2028、孤立代理项、组合字符与非 ASCII 键、数字索引、undefined/null；捕获 actual bytes/hashes，不用新实现生成 expected。
2. 新 contracts serialization 测试是首次为独立字节 seam 建立固定向量；保留现有 PA 配置固定 SHA-256 和旧 receipt 恢复测试。IM approval-configuration 测试补充旧 candidate/configuration 摘要与 DEL 差异，不断言其必须相等。
3. 复用 channels credential 测试：固定合成历史私钥/信封（仅测试生成，无真实秘密）、中文/emoji AAD 与 secret、改 owner/revision 拒绝；跨 IM seal → ChannelKey.open 的测试放 IM 的 control 测试附近，通过真实各 owner 实现，不将另一个包引入生产依赖。测试可直接导入相邻包源码（现有架构禁令针对生产），如测试契约限制则置根 tests 的集成适当位置。
4. integration workflow-control 既有 replay 测试增加含 Unicode prompt、嵌套 schema 的改动前固定 WorkflowCall.key，并从该历史记录重放，防止新旧算法同时变化的假阳性。
5. IM identity 既有 device proof 与迁移测试保留；补固定 serializeIdentityJson 值或 proof，确保 DEL/嵌套不漂移。未改变的 Node 浅排序和 ChannelKey 算法不重复构建另一套测试框架。
6. 先窄测，再按 CI 执行 build/typecheck、全量 Vitest、Python 非 E2E、docs、ruff、ios runtime 与前端检查。iOS 原生路径未改，不跑原生 build job。

## 风险与回退

主要风险是错误导出选择、DEL 或 traversal 漂移及新旧编码互相抵消的 round-trip 假阳性；用改动前固定值和历史信封对照避免。错误即回退代码，不动存量数据。shared 文件不含 Buffer/crypto，不为浏览器拉入加密依赖。

## 一次性部署迁移

无。

## Runbook for Reviewer

无需要启动的常驻服务：验证是纯字节 seam、临时密钥/内存或临时 SQLite 的实际 owner 接口。Review 驱动方式：零用户面，跳过产品 reviewer；静态 reviewer 同次执行 code-review 与 verifier，核对 fixed vector 来源和测试结果。验收前置：本 worktree 的 frozen pnpm dependencies、Node 24.22.1、现有 Python dev environment；无外部账号或生产数据。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-serialization | 明确字节契约并迁移消费者 | 无 | 无 | product-contracts/serialization + exports；IM/Channels/PA/Node/integration workflow 的序列化定义、导入/调用及对应 tests | [reviewer] 零用户面，不派产品 reviewer；[worker] Task 不再导出通用 serializer，所有有效调用按语义接入；Unicode/嵌套固定字节、配置和幂等摘要、历史信封与 IM→ChannelKey 互操作通过；各 owner crypto 不变；必要 CI 通过 |
