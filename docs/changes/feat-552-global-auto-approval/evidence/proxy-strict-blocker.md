# 全局真实旅程的外部代理阻塞

2026-09-12，首次 T3 在隔离 IM/Gateway、Sol 主模型 / Terra 审批模型下未能完成 Inbox(check)。原始 session 为 `sess_eafc21491b8b40e8`。Nano 出站 schema 只要求 `action`，实际模型却两次生成 `{"action":"check","target":"","cursor":"","limit":20}`，被现有 Inbox 业务校验拒绝。临时文件未删除，未形成聊天确认闭环。

## 根因与因果探针

外部仓库 LLM_PROXY `main=92b731616349ab8b26673100be08d7dd0196038b` 的 `proxy_converters.py::_chat_tools_to_responses_tools` 只复制 type/name/description/parameters，丢失或省略 strict。该代码先于 feat-552；不是本 unit 的 Inbox 改动引入。

两个真实 Sol `/v1/responses` 请求使用相同测试 schema（只有 action 必填）和输入，仅改变 strict：

| 请求 | 上游回显 | 实际生成 |
|---|---|---|
| A：省略 strict | strict=true；四个字段均 required | `{"action":"check","target":"","cursor":"","limit":1}` |
| B：strict=false | strict=false；仅 action required | `{"action":"check"}` |

两次均 HTTP 200 / completed；没有执行模型返回的工具。结果直接展示 schema 被改写，不能归因于模型忽略省略参数的提示。Responses 缺省 strict 会规范化 schema，Chat Completions 缺省仍非 strict，见 [OpenAI 官方 function calling 文档](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)。

## 待审修复与边界

外部最小补丁在转换后的 function 对象增加 `"strict": fn.get("strict", False)`，保留显式值，缺省保持源协议的非 strict 语义。隔离提取转换函数测试：原实现 3 failed / 1 passed，内存应用补丁后 4 passed；`git apply --check` 通过。

当前仅准备补丁，尚未应用或重启共享代理。原设计明确不重启本机 :4000；应用及重启已向用户请求授权。未修改 Nano schema、放宽 Inbox 校验或换模型绕过失败。后续授权和复验结果须补录，当前证据不构成 T3 成功。

本机可复核文件：`/tmp/feat552-proxy-strict-probe.md`、`/tmp/feat552-proxy-strict.patch`、`/tmp/feat552-proxy-strict-test.py`。补丁 SHA-256 `1cba7587f5f7baefb7bea79ed2df1f57a6021510dc7a1067b5be38d3857ab8a3`。真实 A/B 的代理 session 标识分别为 `feat552-proxy-strict-A-omitted` 与 `feat552-proxy-strict-B-false`；原始请求保留于外部代理日志，未把身份凭据或运行数据库加入仓库。
