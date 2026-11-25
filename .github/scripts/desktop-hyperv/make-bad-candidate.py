#!/usr/bin/env python3
"""Create a broken 1.0.2 Desktop Windows candidate for automatic rollback testing."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main() -> None:
    v1_dir = Path(sys.argv[1]).resolve()
    v2_dir = Path(sys.argv[2]).resolve()
    v3_dir = Path(sys.argv[3]).resolve()
    v3_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bad-win-stage-") as tmp:
        stage = Path(tmp)
        with tarfile.open(v2_dir / "desktop-app-win32-x64.tar.gz", "r:gz") as tf:
            tf.extractall(stage)

        cli = stage / "apps/node/lib/cli.js"
        orig = cli.read_text(encoding="utf-8")
        prefix = (
            'if (process.argv.includes("start") || process.argv.includes("--foreground")) {\n'
            '  console.error("Simulated 1.0.2 broken startup");\n'
            "  process.exit(1);\n"
            "}\n"
        )
        cli.write_text(prefix + orig, encoding="utf-8")

        bad_tar = v3_dir / "desktop-app-win32-x64.tar.gz"
        with tarfile.open(bad_tar, "w:gz", compresslevel=6) as tf:
            for root, _, files in os.walk(stage):
                for name in sorted(files):
                    p = Path(root) / name
                    tf.add(p, arcname=p.relative_to(stage).as_posix())

    shutil.copy2(
        v2_dir / "desktop-runtime-win32-x64.tar.gz",
        v3_dir / "desktop-runtime-win32-x64.tar.gz",
    )
    shutil.copy2(
        v1_dir / "Crewden-Desktop-Setup-x64.exe",
        v3_dir / "Crewden-Desktop-Setup-x64.exe",
    )

    base = "https://github.com/Mrchen116/nano-multiagent/releases/download/v1.0.2/"
    desc = json.loads((v2_dir / "desktop-win32-x64.json").read_text(encoding="utf-8"))
    desc["version"] = "1.0.2"
    desc["runtime"]["download_url"] = base + desc["runtime"]["name"]
    desc["app"] = {
        "name": "desktop-app-win32-x64.tar.gz",
        "size": bad_tar.stat().st_size,
        "sha256": sha256_file(bad_tar),
        "download_url": base + "desktop-app-win32-x64.tar.gz",
    }
    desc_bytes = (json.dumps(desc, indent=2) + "\n").encode("utf-8")
    (v3_dir / "desktop-win32-x64.json").write_bytes(desc_bytes)

    manifest = json.loads(
        (v1_dir / "manifest.desktop-win32-x64.json").read_text(encoding="utf-8")
    )
    manifest["version"] = "1.0.2"
    manifest["size"] = len(desc_bytes)
    manifest["sha256"] = hashlib.sha256(desc_bytes).hexdigest()
    manifest["download_url"] = base + "desktop-win32-x64.json"
    manifest["installer"]["download_url"] = base + "Crewden-Desktop-Setup-x64.exe"
    (v3_dir / "manifest.desktop-win32-x64.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
