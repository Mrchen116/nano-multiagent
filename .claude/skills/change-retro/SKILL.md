---
name: change-retro
description: "用户明确要求复盘已发生的 change unit 开发过程、耗时、返工或反馈根因时使用；不作为默认交付门禁。"
---

# Change Retro

从用户反馈、原始 session/subagent 轨迹、版本化文档与代码，解释哪一步导致了本次问题，并给出有证据的改进建议。

## 证据约束

- 原始动作和结果优先；DONE、旧 retro、旁人转述与摘要只是线索。区分观察与推断，并保留反证和无法确认项。
- 使用事发时适用的流程、需求和设计判断，不用当前 Skill 倒推历史违规。只读取线索涉及的角色规则，不加载全部 change Skills。
- 区分需求/设计错误、实现偏离、验证不足和编排问题；将症状追到有证据支持的决策或动作，不把“Agent 不行”当归因。
- 耗时/轮次/往返等数字说明采样与分母，区分 active 时间、等待和离线。异常计数是调查线索，不直接等于空转或因果证明。
- 用户纠正后重新查原始证据，错误判断明确撤回；改进建议遵循用户已有约束，不自动新增人工门禁。

## 产物

唯一定位 unit 与相关版本。用 [mine_jsonl.py](scripts/mine_jsonl.py) 的 sessions/humans/subagents/churn/dispatches/dialogue 提取线索，再核原文；格式与命令边界见 [取证参考](references/investigation.md)。

按 [output-template](references/output-template.md) 写新的 `retro-pipeline-rootcause.md`，不覆盖旧复盘。报告包含范围/版本、时间线、每项症状→证据→根因→建议、按 Skill 归并的改进和未决问题。证据充分回答用户的问题后结束；按授权提交，未经要求不直接修改被复盘 Skills。
