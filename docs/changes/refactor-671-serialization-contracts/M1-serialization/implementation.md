# 实施与验证记录

## 兼容基线

字节与合成信封在产品代码修改前由 a34af8473 的原实现生成。可提交固定向量在 contracts serialization 测试、IM configuration/identity/message-attempts 测试、Workflow 历史 replay 测试和 Channels `tests/fixtures/credential-envelopes-v1.json`。fixture 私钥仅为本次离线生成的测试材料，从未用于账号/服务；无生产数据。旧实现脚本和原报告副本保留在本 worktree ignored `output/refactor-671/`，不作为运行依赖。

固定序列化覆盖中文、emoji、DEL/U+0080/U+2028、孤立代理项、组合字符、非 ASCII 与数字索引键、嵌套数组/对象；另核对 missing/null 与原 traversal 差异。配置摘要明确保留 DEL 的既有差异，不声称修复当前协议。旧 IM/Node 信封均由实际 ChannelKey 解封；新 IM seal 既经 ChannelKey 又用固定 AAD/明文字节独立解密，防止 JSON.parse 隐藏转义漂移。Workflow 使用旧 key 重放完成结果，不以新算法生成 expected。

## 测试资产处置

- keep：现有配置 pre-strategy receipt 恢复、Task/迁移、device-binding、Channels revision/owner 拒绝与其他幂等测试，测试中旧名称随生产入口更新。
- extend：上述已有 owner 测试增加固定历史字节/摘要/信封或 replay 输入。
- new：contracts serialization.test.ts 为新公开纯字节 seam 的最低层固定向量；不新建跨层通用测试框架。
- 删除的仅为无消费者的 interactive canonicalJson 实现，没有删除有效测试。

## 已执行

- 改动前基线：Node 24.22.1，4 文件 14 tests passed。
- 初次实现：Node 24.22.1，contracts build、IM typecheck 通过；8 文件 56 tests passed，见本地 `output/refactor-671/narrow-tests.log`。

## 集成边界

从 a34af8473 开始隔离工作；该本地主干的两笔尚未在 origin/main 的文档提交不属于本 PR，实施完成后仅把本 unit 提交 rebase 到远端 main。原报告副本仍在本地工作现场，固定向量保留其原始代码基线。原报告不回写。

另一聊天的 IM 类型职责重构可能与本 PR 在 channels/control/gateway/identity/task-graphs 的 import 或签名附近相交；本任务仅修改 serializer 定义、名称/导入/调用，不改 Row/ImContext 或领域接口。需要保留另一任务的类型改动，同时保留这里选定的字节 encoder。
