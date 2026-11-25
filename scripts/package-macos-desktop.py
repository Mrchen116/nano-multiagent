#!/usr/bin/env python3
"""Assemble Crewden.app (macOS arm64) with seeded Node 24.22.1 runtime/app archives and build Crewden-Desktop-arm64.dmg."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def build_info_plist(version: str) -> bytes:
    short_ver = version if version[0:1].isdigit() else "0.1.0"
    payload = {
        "CFBundleDevelopmentRegion": "zh_CN",
        "CFBundleDisplayName": "Crewden",
        "CFBundleExecutable": "crewden-desktop",
        "CFBundleIconFile": "icon.icns",
        "CFBundleIdentifier": "work.crewden.desktop",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "Crewden",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": short_ver,
        "CFBundleVersion": version[:32],
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSUserNotificationAlertStyle": "alert",
        "CFBundleURLTypes": [
            {
                "CFBundleURLName": "work.crewden.desktop.connect",
                "CFBundleTypeRole": "Viewer",
                "CFBundleURLSchemes": ["crewden-desktop"],
            }
        ],
    }
    return plistlib.dumps(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary",
        type=Path,
        default=ROOT / "apps/desktop/target/release/crewden-desktop",
    )
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist/desktop-release")
    parser.add_argument(
        "--app-out", type=Path, default=ROOT / "dist/desktop/Crewden.app"
    )
    parser.add_argument("--version", default=os.environ.get("RELEASE_VERSION", "0.1.0"))
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--extra-app-note", default="")
    parser.add_argument(
        "--skip-dmg",
        action="store_true",
        help="Only buildarchives without repacking DMG (for v2 update test)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    commit = (
        args.source_commit
        or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    )

    with tempfile.TemporaryDirectory(prefix="crewden-mac-pkg-") as tmp_str:
        tmp = Path(tmp_str)
        placeholder_dmg = tmp / "placeholder.dmg"
        if args.skip_dmg and (out_dir / "Crewden-Desktop-arm64.dmg").is_file():
            shutil.copy2(out_dir / "Crewden-Desktop-arm64.dmg", placeholder_dmg)
        else:
            placeholder_dmg.write_bytes(b"placeholder")

        archive_cmd = [
            "python3",
            str(ROOT / "scripts/build-desktop-archives.py"),
            "--platform",
            "desktop-darwin-arm64",
            "--out-dir",
            str(out_dir),
            "--installer",
            str(placeholder_dmg),
            "--version",
            args.version,
            "--source-commit",
            commit,
        ]
        if args.base_url:
            archive_cmd.extend(["--base-url", args.base_url])
        if args.extra_app_note:
            archive_cmd.extend(["--extra-app-note", args.extra_app_note])
        subprocess.run(archive_cmd, cwd=ROOT, check=True)

        if args.skip_dmg:
            return

        binary = args.binary.resolve()
        if not binary.is_file():
            raise RuntimeError(
                f"Missing release binary at {binary}; build apps/desktop first"
            )

        app_bundle = args.app_out.resolve()
        if app_bundle.exists():
            shutil.rmtree(app_bundle)
        contents = app_bundle / "Contents"
        macos_dir = contents / "MacOS"
        resources_dir = contents / "Resources"
        seed_dir = resources_dir / "seed-archives"
        macos_dir.mkdir(parents=True, exist_ok=True)
        seed_dir.mkdir(parents=True, exist_ok=True)

        (contents / "Info.plist").write_bytes(build_info_plist(args.version))
        shutil.copy2(binary, macos_dir / "crewden-desktop")
        os.chmod(macos_dir / "crewden-desktop", 0o755)
        shutil.copy2(ROOT / "apps/desktop/icons/icon.icns", resources_dir / "icon.icns")

        for asset_name in (
            "manifest.desktop-darwin-arm64.json",
            "desktop-darwin-arm64.json",
            "desktop-runtime-darwin-arm64.tar.gz",
            "desktop-app-darwin-arm64.tar.gz",
        ):
            shutil.copy2(out_dir / asset_name, seed_dir / asset_name)

        subprocess.run(
            ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app_bundle)],
            check=True,
        )

        dmg_stage = tmp / "dmg-root"
        dmg_stage.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app_bundle, dmg_stage / "Crewden.app", symlinks=True)
        os.symlink("/Applications", dmg_stage / "Applications")

        final_dmg = out_dir / "Crewden-Desktop-arm64.dmg"
        final_dmg.unlink(missing_ok=True)
        subprocess.run(
            [
                "/usr/bin/hdiutil",
                "create",
                "-volname",
                "Crewden Desktop",
                "-srcfolder",
                str(dmg_stage),
                "-ov",
                "-format",
                "UDZO",
                str(final_dmg),
            ],
            check=True,
        )

        # Update manifest installer size & sha256 to match the final DMG (descriptor sha256 is unchanged).
        manifest_path = out_dir / "manifest.desktop-darwin-arm64.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["installer"]["size"] = final_dmg.stat().st_size
        manifest["installer"]["sha256"] = sha256_file(final_dmg)
        manifest_bytes = (
            json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        (seed_dir / "manifest.desktop-darwin-arm64.json").write_bytes(manifest_bytes)
        subprocess.run(
            ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app_bundle)],
            check=True,
        )

        print(
            json.dumps(
                {
                    "app_bundle": str(app_bundle),
                    "dmg_path": str(final_dmg),
                    "dmg_bytes": final_dmg.stat().st_size,
                    "dmg_sha256": manifest["installer"]["sha256"],
                    "descriptor_sha256": manifest["sha256"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
