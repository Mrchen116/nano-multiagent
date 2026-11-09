"""Run the bounded context prefix model without writing TLC state into the repo."""

import argparse
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def run_tlc(jar: Path, module: str, work: Path) -> int:
    """Run one scenario and preserve TLC's exit status."""
    command = [os.environ.get("JAVA", "java"), "-XX:+UseParallelGC", "-cp", str(jar),
               "tlc2.TLC", "-workers", "1", module]
    return subprocess.run(command, cwd=work, check=False).returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?", default="all", choices=(
        "all", "baseline", "mixed", "image", "breakpoint", "parallel", "pa-event", "restart", "configuration",
    ))
    parser.add_argument("--agent", choices=("Global", "PA"))
    args = parser.parse_args()
    assets = Path(__file__).resolve().parent
    jar = Path(os.environ["TLA2TOOLS"]).resolve()
    digest = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
    if hashlib.sha256(jar.read_bytes()).hexdigest() != digest:
        raise SystemExit("TLA2TOOLS must point to the pinned TLC v1.7.4 release jar.")

    cases = ("baseline", "mixed", "image", "breakpoint") if args.case == "all" else (args.case,)
    result = 0
    for case in cases:
        if case == "breakpoint":
            with TemporaryDirectory(prefix="nano-context-cache-breakpoint-") as work:
                for name in ("CacheBreakpoint.tla", "CacheBreakpoint.cfg"):
                    shutil.copy(assets / name, work)
                print("TLC breakpoint: Anthropic Messages", flush=True)
                code = run_tlc(jar, "CacheBreakpoint.tla", Path(work))
                result = result or code
            continue
        agents = (args.agent,) if args.agent else ("Global", "PA")
        # TLC stops at the first failure; search each identity independently
        # for a real counterexample.
        partitions = [(agent,) for agent in agents] if case == "image" else [agents]
        for partition in partitions:
            with TemporaryDirectory(prefix="nano-context-cache-prefix-") as work:
                root = Path(work)
                shutil.copy(assets / "ContextCachePrefix.tla", root)
                cfg = (assets / "ContextCachePrefix.cfg").read_text()
                cfg = cfg.replace('{"Global", "PA"}', "{" + ", ".join(f'"{a}"' for a in partition) + "}")
                if case == "mixed":
                    cfg = cfg.replace("MaxRequests = 4", "MaxRequests = 3")
                    cfg = cfg.replace("MaxTools = 4", "MaxTools = 2")
                    cfg = cfg.replace("MaxChanges = 2", "MaxChanges = 4")
                elif case == "image":
                    cfg = cfg.replace("ImagePressure = FALSE", "ImagePressure = TRUE")
                elif case != "baseline":
                    cfg = cfg.replace('Fault = "none"', f'Fault = "{case}"')
                (root / "ContextCachePrefix.cfg").write_text(cfg)
                print(f"TLC {case}: {', '.join(partition)}", flush=True)
                code = run_tlc(jar, "ContextCachePrefix.tla", root)
                result = result or code
    raise SystemExit(result)
