---
name: reverse-engineer-claude-code
description: "用户要求逆向取证 Claude Code 的具体隐藏行为、工具/提示词或运行时契约时使用；普通使用说明和一般开发不触发。"
---

# 逆向研究 Claude Code

产出版本明确、可复现的行为与实现契约。按待解决问题选择官方文档、本地源码、请求轨迹或只读二进制分析，不强制每次走全部证据路径。

## 不变量

- 区分 Official contract、Source observation、Runtime observation、Binary observation 与 Inference；开源重建的空桩不能证明已安装版本不存在某能力。
- 记录被分析版本、commit/dirty 状态与原始证据定位。官方契约引用当前 Anthropic 文档；未找到时说明搜索范围，不宣称不存在。
- 模型与 effort 使用用户现有配置或明确实验约束，不固定旧型号。真实调用限定目标、预算和停止条件；未经授权不扩大写入或成本范围。
- 默认只读，保护本机软件、凭据与无关数据；不得修改二进制、绕过许可/保护。隔离实验现场。
- 捕获的 system/tools/messages 是对应版本与执行分支实际发送的提示词；只重建已有证据支持的层，不编造隐藏提示词或把摘要冒充原文。发布前去除 secret 并标删节。

## 按需参考

- 运行实验或解释请求/响应：读 [experiment-playbook](references/experiment-playbook.md)，使用 [inspect_anthropic_session.py](scripts/inspect_anthropic_session.py)。只有需要精确文本时才展开 system/messages。
- 源码与轨迹仍不能解决重要实现问题：读 [binary-analysis-playbook](references/binary-analysis-playbook.md)，优先检查内嵌脚本和实际调用点。

交付激活条件、编排/工具边界、状态与持久化、权限/失败行为、实现落点和未知项；用实际证据支撑请求涉及的部分即可。重大调查按研究目录规范建带日期资料包并入索引；未经采纳与实现不提升为 current spec。新实验不能改变结论或解决重大矛盾时停止。
