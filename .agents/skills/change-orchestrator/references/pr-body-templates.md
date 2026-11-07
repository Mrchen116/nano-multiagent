# PR body

从最终需求、实际实现和 review.md 提炼问题与结果，按变更大小控制篇幅；不逐条复制模板空项或全部证据。用户明确暂不 PR 时不创建。

组装前读取实际 repository URL 与 PR head SHA。文档链接固定到该提交，不输出相对 docs 链接。Full 链接首文档/design/review，lite 链接 fix/review；快速开发说明 as-built 和实际用户验收，不补造事前阶段。

```markdown
## Summary

<具体问题与结果；必要取舍>

## Documents

- [需求](<repo_url>/blob/<pr_head_sha>/docs/changes/archive/<unit_dir>/<首文档>.md)
- [设计](<repo_url>/blob/<pr_head_sha>/docs/changes/archive/<unit_dir>/design.md)
- [审查与证据](<repo_url>/blob/<pr_head_sha>/docs/changes/archive/<unit_dir>/review.md)

## Validation

| 问题 / 能力 | 结果与证据 | 实际 base → head | 最终有效 base → head / 理由 |
|---|---|---|---|
| <本次实际执行或保留的判断> | <结论、定位、限制> | <executed_base → validated_at> | <effective_base → effective_through；保留或补验依据> |

<相关测试与 CI；必要未验证项；delta 归并目标或 no spec delta>
```

只列实际存在的文档；lite 删除设计链接，不为省略角色写 skipped 行。Related Issues 只引用真实关联并按实际范围决定 Closes/Refs；实现层退出标准由 review 的覆盖结论和证据承接，不把未审查责任留给 PR 模板中的人。PR body 不含秘密、本机原始日志或未发生的验证。
