# 多层加校验(Defense-in-Depth)

## 这是什么

修完一个由非法数据引起的 bug,只在一处加校验感觉就够了。但那一处校验会被**别的代码路径、重构、或 mock** 绕过。

> **核心:在数据流经的每一层都校验,让这个 bug 在结构上不可能再发生。**

单点校验 = "我们修了这个 bug";多层校验 = "我们让这个 bug 不可能"。不同层抓不同情况:入口校验抓掉大多数、业务逻辑抓边界、环境守卫挡特定上下文的危险、调试日志在前几层失效时兜底。

> ⚠️ 与本项目的张力:`change-impl-worker §0.2` **禁止兜底/降级/防御性吞错**。这里说的"多层校验"**不是吞错**——每一层都是**大声失败(raise/assert),不是静默 fallback**。加的是"非法就炸",不是"非法就猜个默认值继续"。两者方向一致:都要让错误无法静默蔓延。

## 四层

**第 1 层:入口校验** —— 在 API 边界拒掉明显非法的输入
```python
def create_project(name: str, working_directory: str):
    if not working_directory or not working_directory.strip():
        raise ValueError("working_directory 不能为空")
    if not os.path.exists(working_directory):
        raise ValueError(f"working_directory 不存在: {working_directory}")
    if not os.path.isdir(working_directory):
        raise ValueError(f"working_directory 不是目录: {working_directory}")
    ...
```

**第 2 层:业务逻辑校验** —— 确保数据对这个操作有意义
```python
def initialize_workspace(project_dir: str, session_id: str):
    if not project_dir:
        raise ValueError("initialize_workspace 需要 project_dir")
    ...
```

**第 3 层:环境守卫** —— 在特定上下文阻止危险操作
```python
def git_init(directory: str):
    # 测试环境下,拒绝在 tmp 目录之外 git init
    if os.environ.get("PYTEST_CURRENT_TEST"):
        norm = os.path.realpath(directory)
        if not norm.startswith(os.path.realpath(tempfile.gettempdir())):
            raise RuntimeError(f"测试期拒绝在 tmp 外 git init: {directory}")
    ...
```

**第 4 层:调试取证** —— 留下足够上下文供事后排查
```python
def git_init(directory: str):
    logger.debug("about to git init", extra={"directory": directory, "cwd": os.getcwd()})
    ...
```

## 怎么用

发现一个 bug 时:
1. **追数据流**——坏值从哪来、在哪被用(见 `root-cause-tracing.md`);
2. **列出所有检查点**——数据流经的每个点;
3. **每层加校验**——入口 / 业务 / 环境 / 调试;
4. **逐层测**——试着绕过第 1 层,验证第 2 层能抓住。

## 关键洞察

四层都必要。测试时每一层都抓到过别的层漏掉的情况:不同代码路径绕过入口校验、mock 绕过业务校验、不同平台的边界需要环境守卫、调试日志暴露了结构性误用。

**别停在单点校验。** 每一层都加——但记住,每一层都是"非法就炸",不是"非法就吞"。
