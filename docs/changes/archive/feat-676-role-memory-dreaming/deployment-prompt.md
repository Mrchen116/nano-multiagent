# feat-676 一次性部署迁移提示词

本文件是未来授权部署时的操作要求，不代表当前授权执行。目标代码及隔离验证尚未交付时不可执行。由 prod-fleet-deploy 在部署包含 feat-676 的版本时发现并采用。

## 适用范围与前提

- 对象：此次部署节点上已有的长期 PA/独立专家。默认 document + Dreaming 开启；文件可显式选择 legacy，网页不能改变模式或旧自动维护设置。
- 旧状态：workspace 的 `.nanoassistant/memory/{USER,MEMORY}.md` 是限额条目库，旧 memory_curation/skill_creation 可能触发父会话 fork 维护。
- 目标状态：新文档库仍在 `.nanoassistant/memory/`，可写旧库在 `.nanoassistant/memory-legacy/`，逐字备份位于 `.nanoassistant/memory-backups/<migration-id>/`。后台 Skill 自进化暂停，skill-creator 固定内置、无需选择，skill_manage 仍按实际工具权限执行。
- 前提：目标版本已有模式隔离、配置解析、手动导入指导、持续历史基线和恢复回执；M1 已在合成副本验证正常、重复执行、中断及回切。部署前核对验收报告，不在生产补跑未完成验收。

## 顺序与最小修改

1. 记录目标 release SHA、节点、各 agentId/workspace/角色及当前模式。确认无独立主体共用同一可写库；有冲突先报告，不能把混合知识自动分发给多个主体。不要修改模型、channel、身份、Task 或无关工具配置。
2. 按 fleet runbook 暂停相关节点 admission，排空/取消旧记忆维护，再停止受影响服务。核实旧写者已退出后复制；不得在旧 writer 仍活跃时替换库。
3. 为每主体建立迁移清单，保存原文件字节、原权限、原配置及 hash；备份目录 0700、文件 0600。备份成功且 hash 一致才继续。既有 git、用户自定义页或非标准文件一并保留，不擅自清理。
4. 将旧活动库完整保存为 memory-legacy。若目标已存在，按原清单和 hash 判断已完成或冲突，不能覆盖较新旧库。新 memory 根建立仅含角色说明和备份导航的 MEMORY.md；不把旧知识自动摘要、改写、复制进新入口。新库已存在时保留，禁止重新初始化覆盖。
5. 使用目标版本的配置模式写回：memoryMode=document（已有明确 legacy 选择则保留）；旧 memory_curation、memoryInterval 映射到 legacyMemory；默认 features.dreaming=true。保留无关工具、Skill 选择、自定义 prompt 和旧内容。对已有显式名单缺少新机制所需能力，记录缺项与实际不可用状态，不以迁移偷偷扩大工具权限。清除废弃 features.skill_creation 和 Skill 名单中 skill-creator 的陈旧选择，其余 Skill 名单/模式、无关工具与权限保持；新版本固定提供 skill-creator，不新增必选 Feature 依赖。验证旧 skill_creation=false、allowlist 未包含及 denylist 曾包含该名的配置都能启动且默认指导可发现，配置往返不再产生选择项。只转换已明确退役的选择键；旧配置未转换时也由目标解析按相同语义处理。
6. 在服务停机的固定持久事件 cut 初始化 document 源基线；记录每根真实 session cursor及启用时间，不用 wall clock 猜最后一条消息。清单必须把基线与这次目录/配置迁移绑定，重复执行不能重置已处理进度。默认不导入启用前聊天。
7. 启动目标版本。原 legacy writer 与新 Dreaming 必须按模式互斥。新版本仅展示 Dreaming 控制，skill-creator 无需用户选择且无技能创建开关，旧记忆/旧自动复盘无用户入口，自动 Skill fork 已停；旧备份可从 status/入口找到，等用户以后在聊天中要求整理。

一次性搬目录、配置转换由部署 Agent 按清单执行，不增加产品每次启动的猜测式历史迁移。产品正常初始化仅面向新建空库。

## 完成与有限生产核对

只读检查：每主体旧内容备份 hash 一致；两活动库分离；新入口存在且无编造事实；有效模式/自动开关与配置一致；旧 Memory 和新 Dreaming 没有同时在途；后台 Skill 无新自动 fork；节点与 relay 恢复。核对当次 ready 及一次已有状态快照，不等待 24h，不发验收消息、不创建 Task/卡片、不强制触发 LLM 或重启演练。

本次生产完成只表示迁移完整性与服务恢复，不替代 S01–S20 产品验收。实际环境、备份位置、SHA、清单和检查结果写本机受保护部署记录，不把生产记忆/原配置/聊天提交到仓库。

## 中断与恢复

- 备份未完成：原库不动，补齐备份；权限或读取错误不当作空库。
- 备份完成、配置未切换：按清单核对目录；继续未完成步骤，不重新抽取或让模型重写。
- 目标服务已产生新文档：保留新库、Git、维护进度；不得用备份覆盖。短期止损可关闭 Dreaming；需要 legacy 时文件切换并走现有配置应用流程。
- 回切 legacy：消费 memory-legacy 的独立旧内容，不自动将新库压缩回旧格式。之后切回 document 继续原文档及进度。版本降级若旧二进制只识别原路径，先停服务并另外保存新库，再按迁移清单恢复旧路径；不能让旧二进制直接打开新 MEMORY.md。

隔离 M1 必须验证上述每个中断点、幂等重入、Git 失败、模式回切及自然语言旧备份导入。生产只应用已验证步骤，具体故障超出记录则停在保留数据的状态并报告。
