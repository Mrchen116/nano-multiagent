#!/usr/bin/env bash
# Usage: scripts/free-ports.sh [N]   # default N=1
# 输出 N 个互不重复的空闲 TCP 端口,空格分隔。
# 用 Python 一次性 bind 完所有 socket 再 close,避免循环过程中内部碰撞。
set -euo pipefail
N="${1:-1}"
python3 - "$N" <<'PY'
import socket, sys
n = int(sys.argv[1])
socks = []
try:
    for _ in range(n):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        socks.append(s)
    print(" ".join(str(s.getsockname()[1]) for s in socks))
finally:
    for s in socks:
        s.close()
PY
