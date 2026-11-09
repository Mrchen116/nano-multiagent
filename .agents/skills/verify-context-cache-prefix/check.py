"""Run the bounded context prefix model without writing TLC state into the repo."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


if __name__ == "__main__":
    assets = Path(__file__).resolve().parent
    jar = Path(os.environ["TLA2TOOLS"]).resolve()
    digest = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
    if hashlib.sha256(jar.read_bytes()).hexdigest() != digest:
        raise SystemExit("TLA2TOOLS must point to the pinned TLC v1.7.4 release jar.")

    with TemporaryDirectory(prefix="nano-context-cache-prefix-") as work:
        for name in ("ContextCachePrefix.tla", "ContextCachePrefix.cfg"):
            shutil.copy(assets / name, work)
        command = [os.environ.get("JAVA", "java"), "-cp", str(jar), "tlc2.TLC",
                   "-workers", "1", "-config", "ContextCachePrefix.cfg", "ContextCachePrefix.tla"]
        raise SystemExit(subprocess.run(command, cwd=work, check=False).returncode)
