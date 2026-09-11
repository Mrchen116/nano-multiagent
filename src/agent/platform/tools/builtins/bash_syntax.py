"""Tree-sitter adapter for the pinned Bash permission policy.

This extracts shell words, never executes or expands a shell. Unsupported or
ambiguous syntax carries a review reason rather than an incomplete argv.
"""

from __future__ import annotations

import re
import json
import shlex
from pathlib import Path
from dataclasses import dataclass, field

from tree_sitter import Language, Node, Parser
import tree_sitter_bash


_LANGUAGE = Language(tree_sitter_bash.language())
_RULES = json.loads(Path(__file__).with_name("bash_readonly_commands.json").read_text())
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_UNICODE_SPACE = re.compile(
    r"[\u00a0\u1680\u2000-\u200b\u2028\u2029\u202f\u205f\u3000\ufeff]"
)
_ESCAPED_SPACE = re.compile(r"\\[ \t]|(?:^|[^ \t\\])(?:\\\\)*\\\n|[ \t](?:\\\\)+\\\n")
_BRACE = re.compile(r"\{[^\s]*(,|\.\.)[^\s]*\}")
_CONTAINERS = {"program", "list", "pipeline", "negated_command"}
_OPERATORS = {"&&", "||", "|", "|&", ";", "!", "\n"}
_REDIRECTS = {"file_redirect", "heredoc_redirect", "herestring_redirect"}
_WORDS = {"word", "number", "raw_string", "string", "concatenation", "command_name"}
_INPUT_OPERATORS = {"<", "<<", "<<-", "<<<", "<&"}
_NUMERIC_TEST = {"-eq", "-ne", "-lt", "-le", "-gt", "-ge"}


@dataclass(frozen=True, slots=True)
class Redirect:
    """An operator and its quote-decoded target."""

    operator: str
    target: str


@dataclass(frozen=True, slots=True)
class SimpleCommand:
    """One parsed command retaining both raw text and argument boundaries."""

    text: str
    argv: tuple[str, ...]
    redirects: tuple[Redirect, ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    has_glob: bool = False


@dataclass(slots=True)
class BashSyntax:
    """Complete analysis, or an explicit reason that proof was unavailable."""

    commands: list[SimpleCommand] = field(default_factory=list)
    assignments: list[str] = field(default_factory=list)
    reason: str | None = None
    command_names: list[tuple[str, str]] = field(default_factory=list)
    literals: dict[str, str | None] = field(default_factory=dict, repr=False)


class _Unsupported(ValueError):
    pass


def _text(node: Node) -> str:
    return node.text.decode("utf-8")


def expansion_kind(command: str) -> str | None:
    """Locate unquoted globs and shell variable expansion, preserving quotes.

    This is the pinned Nlt scan: variables in double quotes still count, while
    single-quoted dollars and quoted filename patterns remain literal data.
    """
    single = double = backtick = escaped = bracket = glob = False
    boundary = True
    index = 0
    while index < len(command):
        char = command[index]
        next_char = command[index + 1 : index + 2]
        index += 1
        if escaped:
            escaped = boundary = False
            continue
        if char == "\\" and not single:
            if next_char == "\n":
                index += 1
                continue
            escaped = True
            continue
        if backtick:
            if char == "`":
                backtick = boundary = False
            continue
        if char == "`" and not single:
            backtick = True
            boundary = False
            continue
        if char == "#" and boundary and not single and not double:
            end = command.find("\n", index)
            index = len(command) if end < 0 else end + 1
            boundary = True
            continue
        if char == "'" and not double:
            single = not single
            boundary = False
            continue
        if char == '"' and not single:
            double = not double
            boundary = False
            continue
        if single:
            continue
        if char == "$" and next_char and re.match(r"[A-Za-z_@*#?!$0-9-]", next_char):
            return "variable"
        if double:
            continue
        if char in " \t\n|&;()<>":
            bracket = False
            boundary = True
            continue
        boundary = False
        if char in "?*":
            glob = True
        elif char == "[":
            bracket = True
        elif char == "]" and bracket:
            glob = True
    return "glob" if glob else None


def _word(node: Node, result: BashSyntax | None = None) -> str:
    kind, raw = node.type, _text(node)
    if kind == "command_name":
        if len(node.named_children) != 1:
            raise _Unsupported("Unresolved command name")
        return _word(node.named_children[0], result)
    if kind == "raw_string":
        return raw[1:-1]
    if kind == "word":
        if _BRACE.search(raw) or re.search(r"\{[^{]*\\}|\{[^}]*\\\{", raw):
            raise _Unsupported("Brace expansion")
        if re.search(r"(?:^|[^\\])(?:\\\\)*[`$'\"]", raw):
            raise _Unsupported("Parser did not resolve shell expansion")
        return re.sub(r"\\(.)", r"\1", raw)
    if kind == "number":
        if node.named_children:
            raise _Unsupported("Arithmetic number contains expansion")
        return raw
    if kind == "string":
        pieces = []
        dynamic = False
        cursor = node.start_byte
        for child in node.children:
            if child.start_byte > cursor:
                gap = node.text[
                    cursor - node.start_byte : child.start_byte - node.start_byte
                ].decode()
                if "`" in gap:
                    raise _Unsupported("Unparsed backtick body in quoted string")
                pieces.append(gap)
            cursor = child.end_byte
            if child.type == '"':
                continue
            if child.type == "string_content":
                pieces.append(
                    re.sub(r'\\([$`"\\])', r"\1", _text(child).replace("\\\n", ""))
                )
            elif child.type == "$":
                pieces.append("$")
            elif child.type == "command_substitution" and result is not None:
                literal = _heredoc_substitution(child)
                if literal is not None:
                    literal = literal.rstrip("\n")
                    if "\n" in literal:
                        if re.match(r"^--?[A-Za-z0-9]", "".join(pieces) + literal):
                            raise _Unsupported(
                                "Heredoc substitution produces option syntax"
                            )
                        pieces.append("\n__CMDSUB_OUTPUT__")
                    else:
                        pieces.append(literal)
                else:
                    _substitution(child, result)
                    pieces.append("__CMDSUB_OUTPUT__")
                    dynamic = True
            elif child.type == "arithmetic_expansion":
                pieces.append(_arithmetic(child))
                dynamic = True
            else:
                raise _Unsupported(f"String contains {child.type}")
        value = "".join(pieces)
        if (
            dynamic
            and len(
                value.replace("__CMDSUB_OUTPUT__", "").replace("__TRACKED_VAR__", "")
            )
            <= 1
        ):
            raise _Unsupported("Quoted expansion has insufficient literal content")
        return value
    if kind == "concatenation":
        if _BRACE.search(raw):
            raise _Unsupported("Brace expansion")
        value = "".join(_word(child, result) for child in node.named_children)
        if "~[" in value or re.match(r"=[a-zA-Z_]", value):
            raise _Unsupported("Zsh dynamic word expansion")
        return value
    if kind == "arithmetic_expansion":
        return _arithmetic(node)
    raise _Unsupported(f"Unsupported argument: {kind}")


def _arithmetic(node: Node) -> str:
    literal = r"(?:[0-9]+|0[xX][0-9a-fA-F]+|[0-9]+#[0-9a-zA-Z]+|[-+*/%^&|~!<>=?:(),]+|<<|>>|\*\*|&&|\|\||[<>=!]=|\$\(\(|\)\))"
    for child in node.children:
        if not child.children:
            if not re.fullmatch(literal, _text(child)):
                raise _Unsupported("Arithmetic expansion references a non-literal")
        elif child.type in {
            "binary_expression",
            "unary_expression",
            "ternary_expression",
            "parenthesized_expression",
        }:
            _arithmetic(child)
        else:
            raise _Unsupported("Arithmetic expansion contains unsupported syntax")
    return "__TRACKED_VAR__"


def _substitution(node: Node, result: BashSyntax) -> None:
    before = len(result.commands)
    literals = result.literals.copy()
    for child in node.named_children:
        _visit(child, result)
    result.literals = literals
    if len(result.commands) == before:
        result.commands.append(SimpleCommand(_text(node), ("true",)))


def _heredoc_substitution(node: Node) -> str | None:
    statements = node.named_children
    if len(statements) != 1 or statements[0].type != "redirected_statement":
        return None
    commands = [
        child for child in statements[0].named_children if child.type == "command"
    ]
    heredocs = [
        child
        for child in statements[0].named_children
        if child.type == "heredoc_redirect"
    ]
    if len(commands) != 1 or len(heredocs) != 1 or _text(commands[0]) != "cat":
        return None
    heredoc = heredocs[0]
    if any(child.type == "<<-" for child in heredoc.children):
        return None
    _redirect(heredoc)
    body = next(
        child for child in heredoc.named_children if child.type == "heredoc_body"
    )
    value = _text(body)
    dangerous_awk = (
        r"(?<![A-Za-z_])system[\s\\]*\(",
        r'(?:^|[^|])\|&?[^/|%";#{}]*"|(?:^|[^|])\|&?[\s\\]*getline\b',
        r"@[\s\\]*(?:load|include)\b|@[\s\\]*\w+(?:::\w+)?(?:\[[^\]]*\])*[\s\\]*\(",
        r"(?<![A-Za-z_])extension[\s\\]*\(",
        r'"/inet[46]?/',
    )
    if re.search(r"/proc/.*/environ", value) or any(
        re.search(pattern, value) for pattern in dangerous_awk
    ):
        raise _Unsupported("Heredoc substitution contains executable program text")
    return value


def _redirect(node: Node, result: BashSyntax | None = None) -> Redirect:
    if node.type == "heredoc_redirect":
        start = next(
            (child for child in node.named_children if child.type == "heredoc_start"),
            None,
        )
        if start is None:
            raise _Unsupported("Missing heredoc delimiter")
        quoted = _text(start).startswith(("'", '"', "\\"))
        body = next(
            (child for child in node.named_children if child.type == "heredoc_body"),
            None,
        )
        if not quoted:
            raise _Unsupported("Unquoted heredoc undergoes shell expansion")
        if body is None:
            raise _Unsupported("Heredoc body was not scanned")
        delimiter = _text(start)
        if delimiter[0] in "\"'" and "\\" in delimiter[1:-1]:
            raise _Unsupported("Quoted heredoc delimiter contains a backslash")
        if any(child.type != "heredoc_content" for child in body.named_children):
            raise _Unsupported("Heredoc body contains unsupported syntax")
        marker = delimiter[1:] if delimiter.startswith("\\") else delimiter[1:-1]
        strip_tabs = any(child.type == "<<-" for child in node.children)
        if strip_tabs and marker.startswith("\t"):
            raise _Unsupported("Tab-prefixed heredoc delimiter")
        for line in _text(body).splitlines():
            line = line.lstrip("\t") if strip_tabs else line
            if (
                marker
                and line.startswith(marker)
                and re.search(r"[)`}]", line[len(marker) :])
            ):
                raise _Unsupported(
                    "Heredoc delimiter can terminate before a shell metacharacter"
                )
        return Redirect("<<", "")
    if node.type == "herestring_redirect":
        words = node.named_children
        if len(words) != 1:
            raise _Unsupported("Unresolved here-string")
        return Redirect("<<<", _word(words[0], result))
    operator = None
    targets = []
    for child in node.children:
        if child.type == "file_descriptor":
            continue
        if child.type in {"<", ">", ">>", ">&", "<&", ">|", "&>", "&>>", ">&-", "<&-"}:
            operator = child.type
        elif child.type == "variable_name":
            raise _Unsupported("Redirect assigns a file descriptor variable")
        else:
            targets.append(_word(child, result))
    if operator in {">&-", "<&-"}:
        raise _Unsupported("Close-fd redirect requires review")
    if not operator or len(targets) != 1:
        raise _Unsupported("Redirect does not have exactly one target")
    if operator in {">&", "<&"} and targets[0].startswith("-"):
        raise _Unsupported("Redirect target hides a close-fd argument")
    if (
        "__CMDSUB_OUTPUT__" in targets[0]
        or "__TRACKED_VAR__" in targets[0]
        or "\n" in targets[0]
        or targets[0].startswith(("!", "="))
    ):
        raise _Unsupported("Redirect target can undergo further shell expansion")
    if operator == ">&" and not re.fullmatch(r"[A-Za-z0-9./_-]+", targets[0]):
        raise _Unsupported("Redirect target undergoes a second word expansion")
    return Redirect(operator, targets[0])


def _assignment(node: Node, result: BashSyntax) -> tuple[str, str]:
    name = node.child_by_field_name("name")
    value = node.child_by_field_name("value")
    if name is None or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", _text(name)):
        raise _Unsupported("Non-scalar variable assignment")
    key = _text(name)
    if value is not None and value.type == "command_substitution":
        _substitution(value, result)
        decoded = "__CMDSUB_OUTPUT__"
    else:
        decoded = "" if value is None else _word(value, result)
    if key == "IFS" or "~" in decoded:
        raise _Unsupported("Assignment changes shell splitting or tilde expansion")
    if key in {"PS4", "PROMPT4"}:
        if (
            "+=" in _text(node)
            or "__CMDSUB_OUTPUT__" in decoded
            or "__TRACKED_VAR__" in decoded
            or not re.fullmatch(
                r"[A-Za-z0-9 _+:./=\[\]-]*",
                re.sub(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", "", decoded),
            )
        ):
            raise _Unsupported("Trace prompt assignment can execute shell code")
    if key in _RULES["integer_variables"] and not re.fullmatch(
        r"(?:0|[1-9][0-9]{0,17})", decoded
    ):
        raise _Unsupported("Integer-attributed shell variable evaluates its value")
    return key, decoded


def _test_words(node: Node, result: BashSyntax) -> list[str]:
    if node.type in _WORDS:
        value = _word(node, result)
        if re.search(r"]].*[;\n&|<>]", value, re.S) or re.search(
            r"(?<![A-Za-z0-9_])]]|]](?![A-Za-z0-9_])", value
        ):
            raise _Unsupported("Quoted test operand can terminate the conditional")
        return [value]
    if node.type in {
        "unary_expression",
        "binary_expression",
        "negated_expression",
        "parenthesized_expression",
        "test_command",
    }:
        result_words = []
        for child in node.children:
            if child.type not in {"[[", "]]", "[", "]"}:
                result_words.extend(_test_words(child, result))
        return result_words
    if node.type in {"regex", "extglob_pattern"}:
        raw = _text(node)
        if re.search(
            r"\$[({[\w#?!*@$'\"+~^=-]|`|[<>]\(|(?<!\\)&|\|\||]]", raw
        ) or raw.startswith("=("):
            raise _Unsupported(
                "Conditional pattern contains shell expansion or separators"
            )
        return [raw]
    if node.type in {
        "test_operator",
        "!",
        "(",
        ")",
        "&&",
        "||",
        "==",
        "=",
        "!=",
        "<",
        ">",
        "=~",
    }:
        return [_text(node)]
    raise _Unsupported(f"Unsupported test operand: {node.type}")


def _visit(
    node: Node, result: BashSyntax, redirects: tuple[Redirect, ...] = ()
) -> None:
    kind = node.type
    if kind in _CONTAINERS:
        literals = result.literals.copy()
        before = len(result.commands)
        for child in node.children:
            if child.type in _OPERATORS:
                continue
            if child.type == "&":
                raise _Unsupported("Background execution defers approval-time checks")
            _visit(child, result, redirects)
        if kind == "pipeline":
            result.literals = {
                key: value if result.literals.get(key) == value else None
                for key, value in literals.items()
            }
        if kind in {"pipeline", "negated_command"} and len(result.commands) == before:
            result.commands.append(SimpleCommand(_text(node), ("true",)))
        return
    if kind == "comment":
        return
    if kind == "redirected_statement":
        attached = redirects + tuple(
            _redirect(child, result)
            for child in node.named_children
            if child.type in _REDIRECTS
        )
        commands = [
            child for child in node.named_children if child.type not in _REDIRECTS
        ]
        if any(
            child.type
            not in {
                "command",
                "pipeline",
                "list",
                "negated_command",
                "declaration_command",
                "unset_command",
            }
            for child in commands
        ):
            raise _Unsupported(
                "Redirected statement contains unsupported command structure"
            )
        if not commands:
            result.commands.append(SimpleCommand(_text(node), (), attached))
        for child in commands:
            _visit(child, result, attached)
        return
    if kind == "variable_assignment":
        before = len(result.commands)
        name, value = _assignment(node, result)
        if name.lower() in _RULES["shell_variables"] or name.lower().startswith(
            ("ld_", "dyld_", "bash_func_")
        ):
            raise _Unsupported("Assignment alters command lookup or execution")
        result.assignments.append(name)
        if before or "__CMDSUB_OUTPUT__" in value or "__TRACKED_VAR__" in value:
            result.literals[name] = None
        elif "+=" in _text(node):
            if name in result.literals:
                existing = result.literals[name]
                result.literals[name] = (
                    existing + value if existing is not None else None
                )
        elif name in result.literals and result.literals[name] != value:
            result.literals[name] = None
        else:
            result.literals[name] = value
        if before == len(result.commands) and "__TRACKED_VAR__" in value:
            result.commands.append(SimpleCommand(_text(node), ("true",)))
        return
    if kind == "command":
        argv, env, attached = [], [], list(redirects)
        for child in node.named_children:
            if child.type == "variable_assignment":
                env.append(_assignment(child, result))
            elif child.type in _REDIRECTS:
                attached.append(_redirect(child, result))
            else:
                value = _word(child, result)
                if re.match(r"^--?[\nA-Za-z0-9_]", value) and (
                    "__CMDSUB_OUTPUT__" in value or "__TRACKED_VAR__" in value
                ):
                    raise _Unsupported("Flag contains runtime-determined content")
                argv.append(value)
        raw = _text(node)
        if "\n" in raw or re.search(r"\$[A-Za-z_]", raw):
            raw = shlex.join((*[f"{key}={value}" for key, value in env], *argv))
        result.commands.append(
            SimpleCommand(
                raw,
                tuple(argv),
                tuple(attached),
                tuple(env),
                expansion_kind(_text(node)) == "glob",
            )
        )
        return
    if kind == "test_command":
        argv = ("[[", *_test_words(node, result))
        result.commands.append(
            SimpleCommand(
                _text(node),
                argv,
                redirects,
                has_glob=expansion_kind(_text(node)) == "glob",
            )
        )
        return
    if kind in {
        "if_statement",
        "while_statement",
        "elif_clause",
        "else_clause",
        "do_group",
    }:
        for child in node.named_children:
            _visit(child, result, redirects)
        return
    if kind == "for_statement":
        for child in node.named_children:
            if child.type == "variable_name":
                name = _text(child)
                if (
                    name
                    in {
                        "IFS",
                        "PS4",
                        "HOME",
                        "PWD",
                        "OLDPWD",
                        "USER",
                        "LOGNAME",
                        "SHELL",
                        "PATH",
                        "HOSTNAME",
                        "UID",
                        "EUID",
                        "PPID",
                        "RANDOM",
                        "SECONDS",
                        "LINENO",
                        "TMPDIR",
                        "BASH_VERSION",
                        "BASHPID",
                        "SHLVL",
                        "HISTFILE",
                    }
                    or name in _RULES["integer_variables"]
                    or name in _RULES["volatile_variables"]
                    or name.lower() in _RULES["shell_variables"]
                ):
                    raise _Unsupported("Loop variable alters shell state")
                if result.literals.get(name) is not None:
                    raise _Unsupported("Loop overwrites a previously tracked literal")
                result.assignments.append(name)
            elif child.type == "do_group":
                _visit(child, result, redirects)
            elif child.type == "command_substitution":
                _substitution(child, result)
            else:
                _word(child, result)
        return
    # Hhe has no case/function/ANSI-string fallback; lRn also excludes groups.
    raise _Unsupported(f"Not a simple read-only command: {kind}")


def parse_bash(command: str) -> BashSyntax:
    """Extract every simple command, failing closed on unresolved syntax.

    Args:
        command: Original shell input, with quotes and case intact.

    Returns:
        The commands and redirections, or a review reason.
    """
    result = BashSyntax()
    if len(command.encode("utf-16-le")) // 2 > 10_000:
        result.reason = "Command too long for read-only analysis"
        return result
    try:
        if _CONTROL.search(command) or _UNICODE_SPACE.search(command):
            raise _Unsupported("Control or Unicode whitespace changes shell parsing")
        if _ESCAPED_SPACE.search(command):
            raise _Unsupported("Backslash-escaped whitespace")
        if "~[" in command or re.search(r"(?:^|[\s;&|])=[a-zA-Z_]|<\d*-\d*>", command):
            raise _Unsupported("Zsh dynamic directory or numeric glob expansion")
        root = Parser(_LANGUAGE).parse(command.encode("utf-8")).root_node
        pending = [root]
        while pending:
            node = pending.pop()
            if node.type == "command":
                name = node.child_by_field_name("name")
                if name is not None:
                    try:
                        result.command_names.append((_word(name), _text(node)))
                    except _Unsupported:
                        pass
            pending.extend(reversed(node.named_children))
        if root.has_error:
            raise _Unsupported("Shell syntax is incomplete or unsupported")
        _visit(root, result)
    except (UnicodeError, _Unsupported) as error:
        result.reason = str(error)
    return result


def redirects_are_readonly(redirects: tuple[Redirect, ...]) -> bool:
    """Match the pinned read-only redirect rules without a sandbox bypass."""
    for redirect in redirects:
        op, target = redirect.operator, redirect.target
        if re.match(r"/dev/(tcp|udp)/", target):
            return False
        if (
            op not in _INPUT_OPERATORS
            and target != "/dev/null"
            and not (op == ">&" and re.fullmatch(r"\d+", target))
        ):
            return False
    return True


def flag_words(command: str) -> tuple[str, ...]:
    """Port E_/GRe's shallow word projection used by the legacy flag table.

    CC's AST security pass and its flag table have different projections: this
    one retains backslashes inside quotes and skips direct arithmetic nodes.
    The complete AST must already have passed the structural security checks.
    """
    root = Parser(_LANGUAGE).parse(command.encode()).root_node
    pending = [root]
    target = None
    while pending:
        node = pending.pop()
        if node.type == "command":
            target = node
            break
        pending.extend(reversed(node.named_children))
    if target is None:
        return ()

    def literal(node: Node) -> str:
        raw = _text(node)
        if node.type == "word":
            return re.sub(r"\\(.)", r"\1", raw)
        if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0]:
            return raw[1:-1]
        return raw

    words = []
    for node in target.named_children:
        if node.type == "variable_assignment":
            continue
        if node.type == "command_name":
            node = node.named_children[0] if node.named_children else node
            if node.type == "concatenation":
                if any(
                    child.type in {"command_substitution", "process_substitution"}
                    for child in node.named_children
                ):
                    words.append(_text(node))
                else:
                    words.append(
                        "".join(literal(child) for child in node.named_children)
                    )
            else:
                words.append(literal(node))
        elif node.type in {"word", "string", "raw_string", "number"}:
            words.append(literal(node))
        elif node.type == "concatenation":
            if any(
                child.type in {"command_substitution", "process_substitution"}
                for child in node.named_children
            ):
                break
            words.append("".join(literal(child) for child in node.named_children))
        elif node.type in {"command_substitution", "process_substitution"}:
            break
    return tuple(words)


def has_shell_expansion(command: str) -> bool:
    """Check the expansion nodes disallowed by sed's literal-command gate."""
    root = Parser(_LANGUAGE).parse(command.encode()).root_node
    pending = [root]
    while pending:
        node = pending.pop()
        if node.type in {
            "command_substitution",
            "process_substitution",
            "expansion",
            "simple_expansion",
            "arithmetic_expansion",
        }:
            return True
        pending.extend(node.named_children)
    return False
