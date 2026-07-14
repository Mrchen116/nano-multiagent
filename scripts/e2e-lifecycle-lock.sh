#!/usr/bin/env bash
# Shared generation lock for scripts/e2e-up.sh and scripts/e2e-down.sh.

e2e_acquire_lifecycle_lock() {
  local wt_root=$1 python_bin=$2 lock_path
  lock_path="$("$python_bin" - "$wt_root" <<'PY'
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

worktree = str(Path(sys.argv[1]).resolve())
override = os.environ.get("NANO_MULTIAGENT_E2E_LIFECYCLE_LOCK_PATH")
if override:
    path = Path(override).expanduser().resolve()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
else:
    root = Path(tempfile.gettempdir()) / (
        f"nano-multiagent-e2e-lifecycle-locks-{os.getuid()}"
    )
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or not stat.S_ISDIR(root.stat().st_mode):
        raise SystemExit("e2e lifecycle lock root is not a private directory")
    root.chmod(0o700)
    digest = hashlib.sha256(worktree.encode()).hexdigest()
    path = root / f"{digest}.lock"
try:
    path.relative_to(Path(worktree))
except ValueError:
    pass
else:
    raise SystemExit("e2e lifecycle lock must live outside the worktree")
print(path)
PY
)" || return 1

  # FD 9 remains open in this shell for the whole up/down generation. Long-lived
  # children explicitly close it at spawn so teardown can acquire the same lock.
  exec 9>> "$lock_path"
  "$python_bin" - "$lock_path" <<'PY'
import fcntl
import os
from pathlib import Path
import stat
import sys

path = Path(sys.argv[1])
fd = 9
os.fchmod(fd, 0o600)
held = os.fstat(fd)
current = path.lstat()
if (
    not stat.S_ISREG(held.st_mode)
    or held.st_nlink != 1
    or not stat.S_ISREG(current.st_mode)
    or current.st_nlink != 1
    or (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino)
):
    raise SystemExit("e2e lifecycle lock is not one stable private inode")
fcntl.flock(fd, fcntl.LOCK_EX)
PY
}
