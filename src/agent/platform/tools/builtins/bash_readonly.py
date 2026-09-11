"""Pinned Claude Code 2.1.267 Bash read-only command and argument checks.

The adjacent JSON contains every entry in the shipped external-user command
table. The algorithms below are the table callbacks, argv fast paths, and
read-only composition rules; no command is executed while checking permission.
"""

from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path
import re
import stat
from typing import Any

from agent.platform.tools.builtins.bash_syntax import (
    BashSyntax,
    SimpleCommand,
    expansion_kind,
    flag_words,
    has_shell_expansion,
    redirects_are_readonly,
)


_DATA = json.loads(Path(__file__).with_name("bash_readonly_commands.json").read_text())
_IS_WINDOWS = os.name == "nt"
_COMMANDS = _DATA["commands"]
_SIMPLE = frozenset(_DATA["simple"])
_XARGS_TARGETS = frozenset(_DATA["xargs"])
_GLOB_COMMANDS = frozenset(
    "ls cat head tail wc stat grep egrep fgrep diff du df echo strings hexdump od nl cut column tr tac rev cmp basename dirname realpath readlink sha256sum sha1sum md5sum cd".split()
)
_ENV_ALLOW = frozenset(
    "GOEXPERIMENT GOOS GOARCH CGO_ENABLED GO111MODULE RUST_BACKTRACE RUST_LOG NODE_ENV PYTHONUNBUFFERED PYTHONDONTWRITEBYTECODE PYTEST_DISABLE_PLUGIN_AUTOLOAD PYTEST_DEBUG ANTHROPIC_API_KEY LANG LANGUAGE LC_ALL LC_CTYPE LC_TIME CHARSET TERM COLORTERM NO_COLOR FORCE_COLOR TZ LS_COLORS LSCOLORS GREP_COLOR GREP_COLORS GCC_COLORS TIME_STYLE BLOCK_SIZE BLOCKSIZE COLUMNS LINES CLICOLOR CLICOLOR_FORCE CI DEBIAN_FRONTEND GIT_TERMINAL_PROMPT".split()
)
_FIND_DANGEROUS = frozenset(
    "-delete -exec -execdir -ok -okdir -fprint -fprint0 -fls -fprintf -files0-from".split()
)
_FIND_VALUES = frozenset(_DATA["find_values"])
_NUMERIC_TEST = frozenset("-eq -ne -lt -le -gt -ge".split())
_INTEGER = re.compile(r"^-?(?:0[xX][0-9a-fA-F]+|[0-9]+#[0-9a-zA-Z]+|[0-9]+)$")
_FLAG = re.compile(r"^-[a-zA-Z0-9_-]")
_DOCKER_CONNECTION = tuple(_DATA["docker_connection"])
_DOCKER_SHORT = frozenset(_DATA["docker_short"])
_VERSION = {
    ("claude", "-h"),
    ("claude", "--help"),
    ("node", "-v"),
    ("node", "--version"),
    ("python", "--version"),
    ("python3", "--version"),
    ("ip", "addr"),
}


def _dynamic(value: str) -> bool:
    return "__CMDSUB_OUTPUT__" in value or "__TRACKED_VAR__" in value


def _windows_unc(value: str, *, operand: bool = False) -> bool:
    """Port P_'s Windows-only UNC/WebDAV and option-operand checks."""
    if not _IS_WINDOWS:
        return False
    if operand:
        nt_prefix = r"^[\\/]\?\?[\\/]"
        if re.match(r"^[\\/]{2}", value) or re.match(nt_prefix, value):
            return True
        if "??" in value and re.match(nt_prefix, ntpath.normpath(value)):
            return True
        if re.match(r"^-[A-Za-z0-9]", value):
            tail = re.sub(r"^(?:-[A-Za-z0-9]+)+", "", value)
            if tail and _windows_unc(tail, operand=True):
                return True
        option = r"^--?[A-Za-z0-9][\w-]*="
        tail = value
        while re.match(option, tail):
            tail = tail.split("=", 1)[1]
        if tail != value and tail and _windows_unc(tail, operand=True):
            return True
    patterns = (
        r"\\\\[^ \t\r\n\f\v\\/]+(?:@(?:\d+|ssl))?(?:[\\/]|$|\s)",
        r"(?:^|[^A-Za-z0-9_])[\\/]\?\?(?:[\\/]|$)",
        r"(?<!:)//[^ \t\r\n\f\v\\/]+(?:@(?:\d+|ssl))?(?:[\\/]|$|\s)",
        r"(?<![:\w])/\\+[^ \t\r\n\f\v\\/]+[\\/]"
        if operand
        else r"/\\{2,}[^ \t\r\n\f\v\\/]",
        r"(?<![:\w])\\+/[^ \t\r\n\f\v\\/]+[\\/]"
        if operand
        else r"\\{2,}/[^ \t\r\n\f\v\\/]",
        r"@SSL@\d+|@\d+@SSL|DavWWWRoot",
        r"^(?:\\\\|//)\d{1,3}(?:\.\d{1,3}){3}[\\/]",
        r"^(?:\\\\|//)\[[\da-fA-F:]+\][\\/]",
    )
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)


def _flag_value(value: str, kind: str) -> bool:
    if kind == "string":
        return True
    if kind == "number":
        return bool(re.fullmatch(r"[0-9]+", value))
    if kind == "char":
        return len(value.encode("utf-16-le")) == 2
    return value == kind if kind in {"{}", "EOF"} else False


def _validate_flags(argv: tuple[str, ...], start: int, config: dict[str, Any]) -> bool:
    flags = config["safeFlags"]
    index = start
    while index < len(argv):
        value = argv[index]
        if not value:
            index += 1
            continue
        if argv[0] == "xargs" and (not value.startswith("-") or value == "--"):
            if value == "--" and index + 1 < len(argv):
                value = argv[index + 1]
            return value in _XARGS_TARGETS
        if value == "--":
            if config.get("respectsDoubleDash", True):
                return True
            index += 1
            continue
        if _FLAG.match(value):
            flag, equal, attached = value.partition("=")
            kind = flags.get(flag)
            if kind is None:
                if argv[0] == "git" and re.fullmatch(r"-\d+", flag):
                    index += 1
                    continue
                if (
                    argv[0] in {"grep", "egrep", "fgrep", "rg"}
                    and not flag.startswith("--")
                    and len(flag) > 2
                ):
                    short, tail = flag[:2], flag[2:]
                    if flags.get(short) in {"number", "string"} and re.fullmatch(
                        r"\d+", tail
                    ):
                        index += 1
                        continue
                if (
                    flag.startswith("--")
                    or len(flag) <= 2
                    or any(flags.get("-" + letter) != "none" for letter in flag[1:])
                ):
                    return False
                index += 1
                continue
            if kind == "none":
                if equal:
                    return False
                index += 1
                continue
            if equal:
                argument = attached
                index += 1
            else:
                if index + 1 >= len(argv) or _FLAG.match(argv[index + 1]):
                    return False
                argument = argv[index + 1]
                index += 2
            if argument.startswith(("__CMDSUB_OUTPUT__", "__TRACKED_VAR__")):
                return False
            if kind == "string" and argument.startswith("-"):
                if not (
                    flag == "--sort"
                    and argv[0] == "git"
                    and re.match(r"^-[a-zA-Z]", argument)
                ):
                    return False
            if not _flag_value(argument, kind):
                return False
        else:
            if _dynamic(value):
                return False
            index += 1
    return True


def _git_format_dangerous(args: tuple[str, ...]) -> bool:
    for index, arg in enumerate(args):
        if re.search(r"%[-+ ]?G|%\(\*?signature", arg):
            return True
        for flag in ("--format", "--pretty", "--sort"):
            value = None
            if arg == flag and index + 1 < len(args):
                value = args[index + 1]
            elif arg.startswith(flag + "="):
                value = arg[len(flag) + 1 :]
            if value is None:
                continue
            if (
                _dynamic(value)
                or "signature" in value
                or re.search(r"%[-+ ]?G|%\(\*?signature", value)
            ):
                return True
            if (
                flag != "--sort"
                and value
                and "%" not in value
                and not value.startswith(("format:", "tformat:"))
                and value
                not in {"oneline", "short", "medium", "full", "fuller", "email", "raw"}
            ):
                return True
    return False


def _list_operation_dangerous(command: str, args: tuple[str, ...]) -> bool:
    if _git_format_dangerous(args):
        return True
    required = {"--contains", "--no-contains", "--points-at", "--sort"}
    if command == "git tag":
        required |= {"--merged", "--no-merged", "--format", "-n"}
    index, previous, listing, ended = 0, "", False, False
    while index < len(args):
        arg = args[index]
        if arg == "--" and not ended:
            ended, previous = True, ""
            index += 1
            continue
        if not ended and arg.startswith("-"):
            if arg in {"--list", "-l"} or (
                not arg.startswith("--")
                and len(arg) > 2
                and "=" not in arg
                and "l" in arg[1:]
            ):
                listing = True
            previous = arg.partition("=")[0]
            index += 2 if "=" not in arg and arg in required else 1
        else:
            if (
                arg
                and not listing
                and not (
                    command == "git branch" and previous in {"--merged", "--no-merged"}
                )
            ):
                return True
            index += 1
    return False


def _docker_dangerous(args: tuple[str, ...]) -> bool:
    for arg in args:
        if any(
            arg == flag
            or arg.startswith(flag + "=")
            or len(flag) == 2
            and len(arg) > 2
            and arg.startswith(flag)
            for flag in _DOCKER_CONNECTION
        ):
            return True
        match = re.match(r"^-([A-Za-z]+)", arg)
        if (
            match
            and len(match[1]) >= 2
            and any(letter in _DOCKER_SHORT for letter in match[1])
        ):
            return True
    return False


def _test_dangerous(args: tuple[str, ...], *, bracket: bool = False) -> bool:
    if not bracket and any(
        arg in {"-v", "-R", "-a", "-o"} or "[" in arg for arg in args
    ):
        return True
    for index, arg in enumerate(args):
        following = args[index + 1] if index + 1 < len(args) else None
        if arg in {"-v", "-R", "-t"} and following is not None:
            if (
                "[" in following
                or _dynamic(following)
                or arg == "-t"
                and not _INTEGER.fullmatch(following)
            ):
                return True
        if arg in _NUMERIC_TEST:
            for operand in args[max(0, index - 1) : index + 2 : 2]:
                if not _INTEGER.fullmatch(operand):
                    return True
    return False


def _callback_dangerous(command: str, args: tuple[str, ...], raw: str) -> bool:
    if command in {
        "git log",
        "git show",
        "git shortlog",
        "git rev-list",
        "git for-each-ref",
    }:
        return _git_format_dangerous(args)
    if command in {"git tag", "git branch"}:
        return _list_operation_dangerous(command, args)
    if command == "git reflog":
        return bool(
            args and not args[0].startswith("-") and args[0] not in {"show", "list"}
        ) or any(arg in {"expire", "delete", "exists", "drop", "write"} for arg in args)
    if command == "git ls-remote":
        if _git_format_dangerous(args):
            return True
        index = 0
        while index < len(args):
            if args[index] == "--":
                return index + 1 < len(args)
            if args[index] and not args[index].startswith("-"):
                return True
            index += 2 if args[index] == "--sort" else 1
        return False
    if command == "git remote":
        return any(arg not in {"-v", "--verbose"} for arg in args)
    if command == "git remote show":
        end = args.index("--") if "--" in args else len(args)
        options = args[:end]
        names = tuple(arg for arg in options if arg != "-n") + args[end + 1 :]
        return (
            len(names) != 1
            or "-n" not in options
            or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_-]*", names[0])
        )
    if command == "sed":
        return has_shell_expansion(raw) or not _sed_readonly(args)
    if command == "help":
        return any(re.search(r"[/\\~]", arg) or _dynamic(arg) for arg in args)
    if command == "man":
        keyword_flags = {"-k", "-f", "--apropos", "--whatis"}
        before_end = args[: args.index("--")] if "--" in args else args
        keyword_mode = any(
            arg in keyword_flags
            or arg.startswith("-")
            and not arg.startswith("--")
            and re.search("[kf]", arg[1:])
            for arg in before_end
        )
        keyword = ended = False
        index = 0
        while index < len(args):
            arg = args[index]
            index += 1
            if not ended and arg == "--":
                ended = True
                continue
            if not ended and arg.startswith("-") and arg != "-":
                if arg in keyword_flags:
                    keyword = True
                elif arg in {"-S", "-s"}:
                    index += 1
                continue
            ended = True
            if (
                _dynamic(arg)
                or keyword_mode
                and arg.startswith("-")
                or not keyword
                and re.search(r"[/\\~]", arg)
            ):
                return True
        return False
    if command == "ps":
        return any(
            not arg.startswith("-") and re.fullmatch(r"[a-zA-Z]*e[a-zA-Z]*", arg)
            for arg in args
        )
    if command == "date":
        index = 0
        while index < len(args):
            arg = args[index]
            index += 1
            if arg.startswith("--") and "=" in arg:
                continue
            if arg.startswith("-"):
                if arg in {"-d", "--date", "-r", "--reference", "--rfc-3339"}:
                    index += 1
            elif not arg.startswith("+"):
                return True
        return False
    if command == "lsof":
        for index, arg in enumerate(args):
            if arg.startswith("+m"):
                return True
            value = (
                arg
                if re.match(r"^-[a-zA-Z]*i\S*@", arg)
                else args[index + 1]
                if re.fullmatch(r"-[a-zA-Z]*i", arg) and index + 1 < len(args)
                else ""
            )
            if "@" in value and re.search(
                r"[a-zA-Z]", value.split("@", 1)[1].split(":", 1)[0]
            ):
                return True
        return False
    if command == "tput":
        forbidden = set(
            "init reset rs1 rs2 rs3 is1 is2 is3 iprog if rf clear flash mc0 mc4 mc5 mc5i mc5p pfkey pfloc pfx pfxl smcup rmcup".split()
        )
        ended = False
        index = 0
        while index < len(args):
            arg = args[index]
            index += 1
            if arg == "--":
                ended = True
            elif not ended and arg.startswith("-"):
                if arg == "-S" or not arg.startswith("--") and "S" in arg:
                    return True
                if arg == "-T":
                    index += 1
            elif arg in forbidden:
                return True
        return False
    if command == "ss":
        positions, ended, index = [], False, 0
        while index < len(args):
            arg = args[index]
            index += 1
            if not ended and arg == "--":
                ended = True
            elif not ended and arg.startswith("-"):
                if arg in {"-f", "--family", "-A", "--query", "--socket"}:
                    index += 1
            else:
                positions.append(arg)
        words = re.split(r"[\s()=!<>&|,]+", " ".join(positions))
        skip = False
        for word in filter(None, words):
            if skip:
                skip = False
                continue
            if word in set(
                "dst src dport sport and or not eq ne ge le gt lt autobound state exclude dev fwmark cgroup".split()
            ):
                skip = word in set(
                    "state exclude dport sport dev fwmark cgroup".split()
                )
                continue
            if (
                re.search(r"[g-zG-Z]", word)
                or re.search(r"[a-fA-F]", word)
                and ("." in word or ":" not in word)
            ):
                return True
        return False
    if command == "pyright":
        return any(arg in {"--watch", "-w"} for arg in args)
    if command in {"docker logs", "docker inspect"}:
        return _docker_dangerous(args)
    if command == "test":
        return _test_dangerous(args)
    raise ValueError(f"Unported Bash command callback: {command}")


def _sed_readonly(args: tuple[str, ...]) -> bool:
    # v7's allowFileWrites=false branch. The richer -i compatibility path is
    # deliberately unreachable in read-only approval (no sandbox/edit grant).
    expressions, explicit, positional, has_files, index = [], False, False, False, 0
    while index < len(args):
        arg = args[index]
        index += 1
        if re.match(r"^-e[wWe]|^-w[eE]", arg):
            return False
        if arg in {"-e", "--expression"} and index < len(args):
            expressions.append(args[index])
            explicit = True
            index += 1
        elif arg.startswith(("--expression=", "-e=")):
            expressions.append(arg.split("=", 1)[1])
            explicit = True
        elif arg.startswith("-"):
            continue
        elif not explicit and not positional:
            expressions.append(arg)
            positional = True
        else:
            has_files = True
            break
    flags = [arg for arg in args if arg.startswith("-") and arg != "--"]

    def valid_flags(allowed: set[str]) -> bool:
        return all(
            all("-" + letter in allowed for letter in flag[1:])
            if not flag.startswith("--") and len(flag) > 2
            else flag in allowed
            for flag in flags
        )

    quiet = any(
        flag in {"-n", "--quiet", "--silent"}
        or flag.startswith("-")
        and not flag.startswith("--")
        and "n" in flag
        for flag in flags
    )
    printing = (
        bool(expressions)
        and quiet
        and valid_flags(
            {
                "-n",
                "--quiet",
                "--silent",
                "-E",
                "--regexp-extended",
                "-r",
                "-z",
                "--zero-terminated",
                "--posix",
            }
        )
        and all(
            re.fullmatch(r"(?:\d+|\d+,\d+)?p", part.strip())
            for expression in expressions
            for part in expression.split(";")
        )
    )
    substitution = False
    if (
        not has_files
        and len(expressions) == 1
        and valid_flags({"-E", "--regexp-extended", "-r", "--posix"})
    ):
        expression = expressions[0].strip()
        if expression.startswith("s/"):
            delimiters = list(re.finditer(r"(?<!\\)(?:\\\\)*/", expression[2:]))
            if len(delimiters) == 2:
                suffix = expression[2:][delimiters[-1].end() :]
                substitution = (
                    bool(re.fullmatch(r"[gpimIM]*[1-9]?[gpimIM]*", suffix))
                    and ";" not in expression
                )
    if not printing and not substitution:
        return False
    for expression in expressions:
        if _sed_dangerous(expression):
            return False
    return True


def _sed_dangerous(expression: str) -> bool:
    value = expression.strip()
    if not value:
        return False
    if re.search(r"[^\x01-\x7f]|[{}\n\r]", value):
        return True
    hash_index = value.find("#")
    if hash_index >= 0 and not (hash_index > 0 and value[hash_index - 1] == "s"):
        return True
    patterns = (
        r"^!|[/\d$]!",
        r"\d\s*~\s*\d|,\s*~\s*\d|\$\s*~\s*\d",
        r"^,|,\s*[+-]",
        r"s\\|\\[|#%@]",
        r"\\/.*[wW]",
        r"/[^/]*\s+[wWeE]",
    )
    if any(re.search(pattern, value) for pattern in patterns):
        return True
    if value.startswith("s/") and not re.fullmatch(r"s/[^/]*/[^/]*/[^/]*", value):
        return True
    if (
        re.match(r"^s.", value)
        and re.search(r"[wWeE]$", value)
        and not re.fullmatch(r"s([^\\\n]).*?\1.*?\1[^wWeE]*", value)
    ):
        return True
    address = r"(?:\d+|\$|/[^/]*/[IMim]*|\d+,\d+|\d+,\$|/[^/]*/[IMim]*,/[^/]*/[IMim]*)?"
    if re.match(r"^" + address + r"\s*(?:[wW]\s*\S+|e)", value):
        return True
    match = re.search(r"s([^\\\n]).*?\1.*?\1(.*?)$", value)
    if match and re.search("[wWeE]", match[2]):
        return True
    return bool(re.search(r"y([^\\\n])", value) and re.search("[wWeE]", value))


def _printf_readonly(argv: tuple[str, ...]) -> bool:
    if len(argv) > 1 and argv[1].startswith("-") and argv[1] != "--":
        return False
    start = 2 if len(argv) > 1 and argv[1] == "--" else 1
    fmt = argv[start] if len(argv) > start else ""
    if _dynamic(fmt) or "$" in fmt:
        return False
    fmt = fmt.replace("%%", "")
    if re.search(r"%[^%a-zA-Z]*[lLhqjzZt]*\\[0-7xX]|\\[uU]", fmt):
        return False
    if re.search(r"%[-+ 0#']*[0-9.*]*[lLhqjzZt]*[diouxXeEfFgGaAn]|%[^%a-zA-Z]*\*", fmt):
        number = r"[-+]?(?:0[xX][0-9a-fA-F]+|[0-9]+#[0-9a-zA-Z]+|[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)"
        return all(re.fullmatch(number, arg) for arg in argv[start + 1 :])
    return True


def _strip_shell_wrappers(argv: tuple[str, ...]) -> tuple[str, ...]:
    while argv:
        if argv[0] == "command":
            index = 1
            while index < len(argv) and re.fullmatch(r"-p+", argv[index]):
                index += 1
            if index < len(argv) and argv[index] == "--":
                index += 1
            if index >= len(argv) or argv[index].startswith("-"):
                break
        elif argv[0] == "builtin":
            index = 2 if len(argv) > 1 and argv[1] == "--" else 1
            if index >= len(argv):
                break
        elif argv[0] == "noglob" and len(argv) > 1:
            index = 1
        else:
            break
        argv = argv[index:]
    return argv


def _argv_readonly(argv: tuple[str, ...]) -> bool | None:
    if not argv:
        return False
    name, args = argv[0], argv[1:]
    if name in {"pwd", "whoami", "alias"}:
        return len(argv) == 1
    if argv in _VERSION or name in _SIMPLE:
        return True
    for command in _DATA["external"]:
        prefix = tuple(command.split())
        if argv[: len(prefix)] == prefix:
            return not _docker_dangerous(argv) and not any(
                _dynamic(arg) for arg in argv[len(prefix) :]
            )
    if name in {"echo", "ls"}:
        return True
    if name == "printf":
        return _printf_readonly(argv)
    if name == "[[":
        return not _test_dangerous(args, bracket=True)
    if name == "cd":
        return len(argv) <= 2
    if name == "find":
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in _FIND_DANGEROUS or _dynamic(arg):
                return False
            index += (
                2
                if arg in _FIND_VALUES or re.fullmatch(r"-newer[aBcm][aBcmt]", arg)
                else 1
            )
        return True
    if name == "history":
        return len(argv) == 1 or len(argv) == 2 and bool(re.fullmatch(r"\d+", argv[1]))
    if name == "arch":
        return len(argv) == 1 or args in (("-h",), ("--help",))
    if name == "ifconfig":
        return len(argv) == 1 or len(argv) == 2 and bool(re.match(r"[a-zA-Z]", argv[1]))
    return None


def _table_readonly(argv: tuple[str, ...], raw: str) -> bool:
    wrapper = r"^(?:(?:command(?:[ \t]+-p+)*|builtin)(?:[ \t]+--)?|noglob)[ \t]+(?!-)"
    while re.match(wrapper, raw):
        raw = re.sub(wrapper, "", raw)
    argv = flag_words(raw)
    for command, config in _COMMANDS.items():
        if _IS_WINDOWS and command == "xargs":
            continue
        prefix = tuple(command.split())
        if argv[: len(prefix)] != prefix:
            continue
        args = argv[len(prefix) :]
        if command == "git ls-remote" and any(
            arg == "-o"
            or arg.startswith("--server-option")
            or arg != "--"
            and (arg == "-" or not arg.startswith("-"))
            for arg in args
        ):
            return False
        if any(
            "$" in arg or "{" in arg and ("," in arg or ".." in arg) for arg in args
        ):
            return False
        if not _validate_flags(argv, len(prefix), config):
            return False
        if config.get("regex") and not re.search(config["regex"], raw):
            return False
        if not config.get("regex") and "`" in raw:
            return False
        if argv[0] in {"rg", "grep", "egrep", "fgrep"} and re.search(r"[\r\n]", raw):
            return False
        return not config.get("check") or not _callback_dangerous(command, args, raw)
    # The two regex-only command forms outside Jxn.
    if argv and argv[0] == "uniq":
        return bool(
            re.fullmatch(
                r"uniq(?:\s+(?:-[a-zA-Z]+|--[a-zA-Z-]+(?:=\S+)?|-[fsw]\s+\d+))*(?:\s|$)\s*",
                raw,
            )
        )
    if argv and argv[0] == "jq":
        forbidden = r"(?:\s['\"]?-[a-zA-Z]*[fL]|--from-file|--rawfile|--slurpfile|--run-tests|--library-path|\benv\b|\$ENV\b|\binclude\b|\bimport\b)"
        shape = r"""jq(?:\s+(?:-[a-zA-Z]+|--[a-zA-Z-]+(?:=\S+)?))*(?:\s+'[^'`]*'|\s+"[^"`]*"|\s+[^-\s'\"][^\s]*)+\s*"""
        return not re.search(forbidden, raw) and bool(re.fullmatch(shape, raw))
    return False


def _security_reason(command: SimpleCommand, argv: tuple[str, ...]) -> str | None:
    wrapped = command.argv
    previous = None
    while wrapped and wrapped[0] in {"command", "builtin", "noglob"}:
        name = wrapped[0]
        if previous in {"command", "builtin"} and name == "noglob":
            return "Wrapped noglob has different Bash and zsh execution semantics"
        previous = name
        wrapped = wrapped[1:]
        while wrapped and (wrapped[0] == "--" or re.fullmatch(r"-p+", wrapped[0])):
            wrapped = wrapped[1:]
    if not argv or not argv[0] or _dynamic(argv[0]):
        return "Command name is not statically known"
    if argv[0] == "alias":
        return "Alias evaluates arguments as shell code"
    if any(
        re.search(r"/proc/.*/environ", arg)
        for arg in (*argv, *(red.target for red in command.redirects))
    ):
        return "Access to process environment requires review"
    if any(
        re.search(r"\n\s*#", arg)
        for arg in (
            *argv,
            *(value for _, value in command.env),
            *(red.target for red in command.redirects),
        )
    ):
        return "Quoted newline can conceal arguments from path checks"
    if argv[0] == "find":
        if command.has_glob:
            return "find glob may expand into an action"
        index = 1
        while index < len(argv):
            arg = argv[index]
            if arg in _FIND_DANGEROUS:
                return "find action executes or writes"
            if arg in _FIND_VALUES or re.fullmatch(r"-newer[aBcm][aBcmt]", arg):
                index += 2
                continue
            if _dynamic(arg) or re.search(r"[\[\]*?]", arg):
                return "find argument may expand into an action"
            index += 1
    if argv[0] == "jq" and any(
        re.search(r"\bsystem\s*\(|\b(?:include|import)\b", arg)
        or re.match(
            r"^(?:-[A-Za-z]*[fL]|--(?:from-file|rawfile|slurpfile|library-path)(?:$|=))",
            arg,
        )
        for arg in argv
    ):
        return "jq program can execute code or load files"
    if argv[0] == "printf" and any(
        _dynamic(arg) or "[" in arg and re.search(r"[$`]", arg) for arg in argv[1:]
    ):
        return "printf operand can be arithmetically evaluated by the shell"
    return None


def _git_directory_reason(cwd: Path) -> str | None:
    """Port fSe's bare-repository and plantable gitdir detection."""
    cwd = cwd.resolve()

    def valid_head(directory: Path) -> bool:
        try:
            head = directory / "HEAD"
            metadata = head.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 4096:
                return False
            content = head.read_text()[:255]
            return bool(
                re.match(
                    r"^ref:[ \t]*refs/|^[0-9a-f]{40}(?:[0-9a-f]{24})?[ \t\n\r]*$",
                    content,
                )
            )
        except (OSError, UnicodeError):
            return False

    def repository_state(directory: Path) -> str:
        dotgit = directory / ".git"
        try:
            metadata = dotgit.lstat()
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    valid_head(dotgit)
                    and all(
                        (dotgit / item).is_dir() and os.access(dotgit / item, os.X_OK)
                        for item in ("objects", "refs")
                    )
                    and not (dotgit / "commondir").exists()
                ):
                    return "trusted"
                return "none"
            if stat.S_ISLNK(metadata.st_mode):
                target = Path(os.readlink(dotgit))
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_size > 4096:
                    return "oversized"
                content = dotgit.read_text()
                if "\x00" in content:
                    return "plantable"
                if not content.startswith("gitdir: "):
                    return "none"
                target = Path(content[8:].rstrip("\r\n"))
            else:
                return "none"
            if not target.is_absolute():
                target = directory / target
            try:
                resolved = target.resolve(strict=True)
            except (OSError, RuntimeError):
                return "plantable"
            if (
                resolved == cwd
                or cwd in resolved.parents
                or not any(part.lower() == ".git" for part in resolved.parts)
            ):
                return "plantable"
            return "trusted" if valid_head(resolved) else "none"
        except (OSError, UnicodeError):
            return "none"

    directory = cwd
    while True:
        state = repository_state(directory)
        if state in {"plantable", "oversized"}:
            return "Git directory indirection is not a trusted repository path"
        if state == "trusted":
            return None
        try:
            head = (directory / "HEAD").lstat()
            if stat.S_ISREG(head.st_mode) or stat.S_ISLNK(head.st_mode):
                return "Working directory has bare Git repository indicators"
        except OSError:
            pass
        if any((directory / name).exists() for name in ("objects", "refs")):
            return "Working directory has bare Git repository indicators"
        if directory.parent == directory:
            return None
        directory = directory.parent


def readonly_reason(
    command: str, syntax: BashSyntax, *, cwd: Path | None = None
) -> str | None:
    """Return why a command requires review, or None when fully read-only.

    Args:
        command: Original shell input.
        syntax: Complete tree-sitter analysis for that same input.
        cwd: Effective tool working directory, defaulting to process cwd.

    Returns:
        A review reason, or None for the read-only fast path.
    """
    if syntax.reason:
        return syntax.reason
    if not syntax.commands:
        return "No read-only command found"
    if any(
        name not in _ENV_ALLOW and name in os.environ for name in syntax.assignments
    ):
        return "Bare assignment changes an existing environment variable"
    if expansion_kind(command) == "variable":
        return "Command contains shell variable expansion"
    if _windows_unc(command):
        return "Windows UNC path may access a WebDAV endpoint"
    argvs = [_strip_shell_wrappers(item.argv) for item in syntax.commands]
    if any(argv and argv[0] == "git" for argv in argvs) and any(
        argv and argv[0] == "cd" for argv in argvs
    ):
        return "Compound cd and git require path-aware permission checks"
    if any(argv and argv[0] == "git" for argv in argvs):
        reason = _git_directory_reason(cwd or Path.cwd())
        if reason:
            return reason
    for item, argv in zip(syntax.commands, argvs, strict=True):
        reason = _security_reason(item, argv)
        if reason:
            return reason
        if not redirects_are_readonly(item.redirects):
            return "Output redirection can write files or access a network device"
        if any(name not in _ENV_ALLOW for name, _ in item.env):
            return "Environment prefix is not allowlisted"
        operands = (
            *item.argv,
            *(r.target for r in item.redirects if r.operator == "<"),
        )
        if any(_windows_unc(value, operand=True) for value in operands) or (
            _IS_WINDOWS
            and any(
                re.search(r"(?<![:\w])[\\/]{2,}[^ \t\r\n\f\v\\/]", value)
                for value in operands
            )
        ):
            return "Windows UNC operand may access a WebDAV endpoint"
        if item.has_glob:
            if not argv or argv[0] not in _GLOB_COMMANDS:
                return "Glob expansion can alter command arguments"
            continue
        simple = _argv_readonly(argv)
        if simple is False:
            return "Command arguments are not read-only"
        if simple is None:
            raw = item.text
            if not _table_readonly(argv, raw):
                return "Command or flags require further permission checks"
    return None
