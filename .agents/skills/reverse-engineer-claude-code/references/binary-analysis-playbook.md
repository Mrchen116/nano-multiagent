# 已安装包与二进制文件分析手册

只有三条主要证据路径仍留下影响实现决策的重大问题时，才升级到本手册。优先使用能够回答问题的最高层级产物；原生反汇编是最后一步，而不是第一步。

## 证据阶梯

1. **软件包表面** — 定位可执行文件，检查包元数据、wrapper、相邻源码、source map、类型声明和版本。
2. **二进制身份** — 记录 `claude --version` 的输出、文件路径、类型、架构、大小、代码签名、链接库和构建或运行时标记。
3. **功能字符串** — 搜索精确的工具错误、schema 字段、通知文本、环境变量和生成产物名称。
4. **内嵌源码** — 打包的 Bun/Node/Deno 二进制文件通常包含压缩的 JavaScript。检查原生指令前，先恢复功能特定的“验证 → 编译 → 执行”调用链。
5. **原生符号与反汇编** — 只有行为由原生代码实现，或内嵌源码无法回答判别问题时才使用。
6. **动态观察** — 只有静态证据仍有歧义，且不会暴露凭据或改变行为时，才使用进程/文件追踪或调试器附加。

## 只读基线

以下是有代表性的 macOS 命令：

```bash
BIN="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$(command -v claude)")"
claude --version
file "$BIN"
otool -L "$BIN"
codesign -dvv "$BIN"
strings -a "$BIN" | rg 'Workflow launched|resumeFromRunId|journal\.jsonl'
```

不要复用 `HOME` 等宽泛系统变量。不得修改、重新签名、向可执行文件注入库或重新分发该文件。

## 打包 JavaScript 分析流程

当二进制文件包含 Bun/JavaScriptCore 等 JavaScript 运行时时：

1. 搜索精确功能字符串，记录全部字节偏移。
2. 在功能字符串附近提取一小段可打印窗口供本地检查；不要提交厂商 bundle dump。
3. 识别功能特定的函数边界，以及 parser、VM、worker、process 或文件系统 API 等 import。
4. 沿验证、编译、启动和执行过程追踪同一组压缩标识符。
5. 必须找到实际调用点链路，才能断定功能使用了某个打包库。

证据强度示例：

- `node:vm` 出现在 Bun 二进制文件中的某处 — 弱证据；它可能只是运行时附带内容。
- Workflow 编译器构造 `new vm.Script(...)`，launcher 把该对象传给 runner，且 runner 调用 `runInContext(...)` — 强证据。
- bundle 中包含 Acorn — 弱证据。
- Workflow 元数据 parser 调用 Acorn、遍历生成的 AST、拒绝部分节点，然后重写选定的 await/return/yield 区间 — 强证据。

## 来源记录

```text
installed_version:
binary_path:
file_format_arch:
signer:
runtime_markers:
feature_needles:
byte_offsets:
call_chain:
observation:
limit:
```

压缩函数名和字节偏移只适用于对应 build，不得把它们描述为稳定公开 API。区分：

- **package observation** — 与二进制文件一同发布的 wrapper、manifest 或源码；
- **binary observation** — 已记录安装版本中的精确字节或内嵌调用点；
- **inference** — 无法由恢复的调用链直接证明的解释。

## 停止条件

恢复出的调用链能够回答判别问题时立即停止。不要仅为让调查显得更深入而继续反汇编。如果字符串或内嵌源码暴露了秘密、个人数据、凭据或无关专有内容，不要复制或报告它们。
