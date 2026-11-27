#!/usr/bin/env python3
"""Sign a tested Mac candidate, or independently inspect the final DMG on macOS."""

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DMG = "Crewden-Desktop-arm64.dmg"
DESC = "desktop-darwin-arm64.json"
MANIFEST = "manifest." + DESC
ARCHIVES = {kind: f"desktop-{kind}-darwin-arm64.tar.gz" for kind in ("runtime", "app")}
# Mach-O 64-bit (little endian) and universal binary magics.
MACHO = {bytes.fromhex(h) for h in ("cffaedfe", "cafebabe", "cafebabf")}


def run(*args):
    subprocess.run(args, check=True)


def output(*args):
    return subprocess.check_output(args, text=True)


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, data):
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )


def metadata(path):
    with path.open("rb") as reader:
        return {
            "size": path.stat().st_size,
            "sha256": hashlib.file_digest(reader, "sha256").hexdigest(),
        }


def verify_hash(path, expected):
    if any(expected[k] != v for k, v in metadata(path).items()):
        raise ValueError(f"Release checksum or size mismatch: {path}")


@contextmanager
def mounted(dmg, tmp):
    mount = tmp / "mount"
    mount.mkdir()
    run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, dmg)
    try:
        yield mount / "Crewden.app"
    finally:
        run("hdiutil", "detach", mount)


def check_target(path, floor):
    build = output("xcrun", "vtool", "-arch", "arm64", "-show-build", path)
    minimum = re.search(
        r"platform MACOS\s+minos ([\d.]+)|cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version ([\d.]+)",
        build,
    )
    if not minimum:
        raise ValueError(f"{path.name}: missing macOS arm64 deployment target")
    version = minimum[1] or minimum[2]

    def parts(value):
        return tuple(map(int, (value.split(".") + ["0", "0"])[:3]))

    if parts(version) > parts(floor):
        raise ValueError(
            f"{path.name} requires macOS {version}, above declared {floor}"
        )
    print(f"{path.name}: arm64 macOS {version} (declared {floor})", flush=True)


def sign(path, identity, *extra):
    run("codesign", "--force", "--sign", identity, "--timestamp", *extra, path)


def notarize(path, staple_target, profile):
    result = json.loads(
        output(
            "xcrun",
            "notarytool",
            "submit",
            path,
            "--keychain-profile",
            profile,
            "--wait",
            "--output-format",
            "json",
        )
    )
    print(f"Notary submission {result['id']}: {result['status']}", flush=True)
    if result["status"] != "Accepted":
        raise ValueError(f"Apple rejected {path.name} (submission {result['id']})")
    run("xcrun", "stapler", "staple", staple_target)
    run("xcrun", "stapler", "validate", staple_target)


def native_file(reader, binary):
    magic = reader.read(4)
    reader.seek(0)
    if magic not in MACHO:
        return False
    with binary.open("wb") as writer:
        shutil.copyfileobj(reader, writer)
    # Java class files share the universal Mach-O magic.
    if "Mach-O" in output("file", "-b", binary):
        return True
    reader.seek(0)
    return False


def prepare_archive(archive, tmp, identity):
    # Stage native code separately so its signed bytes are covered by both
    # the seed descriptor and the OTA checksum.
    with tempfile.TemporaryDirectory(dir=tmp) as staging:
        staging = Path(staging)
        with (
            tarfile.open(archive) as src,
            tarfile.open(staging / "signed.tgz", "w:gz", compresslevel=6) as dest,
        ):
            changed = False
            for item in src:
                if not item.isfile():
                    raise ValueError(f"Unexpected non-file archive member: {item.name}")
                with src.extractfile(item) as reader:
                    binary = staging / "code"
                    if not native_file(reader, binary):
                        dest.addfile(item, reader)
                        continue
                    extra = [
                        "--options",
                        "runtime",
                        "--identifier",
                        Path(item.name).name,
                    ]
                    if item.name == "bin/node":
                        extra += [
                            "--entitlements",
                            Path(__file__).with_name("node-entitlements.plist"),
                        ]
                    sign(binary, identity, *extra)
                    item.size = binary.stat().st_size
                    with binary.open("rb") as signed:
                        dest.addfile(item, signed)
                    changed = True
        if changed:
            shutil.move(staging / "signed.tgz", archive)


def verify_archive(archive, tmp, floor, requirement):
    found_node = False
    with tarfile.open(archive) as src:
        for item in src:
            binary = tmp / Path(item.name).name
            with src.extractfile(item) as reader:
                if not native_file(reader, binary):
                    continue
            if requirement:
                run("codesign", "--verify", "--strict", "-R", requirement, binary)
            # pnpm also ships an optional, x86_64-only reflink addon.
            if "arm64" in output("lipo", "-archs", binary).split():
                check_target(binary, floor)
                found_node |= item.name == "bin/node"
            binary.unlink()
    if archive.name == ARCHIVES["runtime"] and not found_node:
        raise ValueError("Missing arm64 bin/node in the runtime seed")


def sign_candidate(candidate, target, identity, profile):
    if not identity.startswith("Developer ID Application: ") or not profile:
        raise ValueError(
            "A Developer ID Application identity and notarytool keychain profile are required"
        )
    if target.exists():
        raise ValueError("Use a fresh output directory for the signed candidate")
    candidate_manifest = read_json(candidate / MANIFEST)
    verify_hash(candidate / DMG, candidate_manifest["installer"])
    with tempfile.TemporaryDirectory(dir=target.parent) as work:
        tmp = Path(work)
        stage = tmp / "volume"
        stage.mkdir()
        app = stage / "Crewden.app"
        with mounted(candidate / DMG, tmp) as source:
            run("ditto", source, app)
        os.symlink("/Applications", stage / "Applications")
        seed = app / "Contents/Resources/seed-archives"
        verify_hash(seed / DESC, candidate_manifest)
        desc = read_json(seed / DESC)
        manifest = read_json(seed / MANIFEST)
        release = tmp / "release"
        release.mkdir()
        for kind, name in ARCHIVES.items():
            verify_hash(seed / name, desc[kind])
            prepare_archive(seed / name, tmp, identity)
            desc[kind].update(metadata(seed / name))
            shutil.copyfile(seed / name, release / name)
        write_json(seed / DESC, desc)
        manifest.update(metadata(seed / DESC))
        write_json(seed / MANIFEST, manifest)
        shutil.copyfile(seed / DESC, release / DESC)
        sign(app, identity, "--options", "runtime")
        run("ditto", "-c", "-k", "--keepParent", app, tmp / "app.zip")
        notarize(tmp / "app.zip", app, profile)
        dmg = release / DMG
        run(
            "hdiutil",
            "create",
            "-volname",
            "Crewden Desktop",
            "-srcfolder",
            stage,
            "-format",
            "UDZO",
            dmg,
        )
        sign(dmg, identity, "--identifier", "work.crewden.desktop.dmg")
        notarize(dmg, dmg, profile)
        manifest["installer"].update(metadata(dmg))
        manifest["macos_distribution"] = "developer-id-notarized"
        write_json(release / MANIFEST, manifest)
        release.rename(target)


def verify(directory, unsigned_test, team):
    dmg = directory / DMG
    manifest = read_json(directory / MANIFEST)
    verify_hash(dmg, manifest["installer"])
    requirement = None
    if not unsigned_test:
        if not re.fullmatch(r"[A-Z0-9]{10}", team):
            raise ValueError("The expected Developer ID team is required")
        requirement = f'anchor apple generic and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "{team}"'
        run("codesign", "--verify", "--strict", "-R", requirement, dmg)
        run("xcrun", "stapler", "validate", dmg)
        run(
            "spctl",
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
            "-vv",
            dmg,
        )
    with tempfile.TemporaryDirectory() as work:
        tmp = Path(work)
        with mounted(dmg, tmp) as app:
            seed = app / "Contents/Resources/seed-archives"
            verify_hash(seed / DESC, manifest)
            desc = read_json(seed / DESC)
            for kind, name in ARCHIVES.items():
                verify_hash(seed / name, desc[kind])
                verify_hash(directory / name, desc[kind])
            verify_hash(directory / DESC, manifest)
            floor = read_json(ROOT / "apps/desktop/tauri.conf.json")["bundle"]["macOS"][
                "minimumSystemVersion"
            ]
            actual = plistlib.loads((app / "Contents/Info.plist").read_bytes())[
                "LSMinimumSystemVersion"
            ]
            if actual != floor:
                raise ValueError(f"DMG declares macOS {actual}, expected {floor}")
            check_target(app / "Contents/MacOS/crewden-desktop", floor)
            with tempfile.TemporaryDirectory(dir=tmp) as native_tmp:
                for name in ARCHIVES.values():
                    verify_archive(seed / name, Path(native_tmp), floor, requirement)
            installed = tmp / "Crewden.app"
            run("ditto", app, installed)
        if not unsigned_test:
            run(
                "xattr",
                "-w",
                "com.apple.quarantine",
                "0083;00000000;CrewdenDistributionCheck;",
                installed,
            )
            run(
                "codesign",
                "--verify",
                "--deep",
                "--strict",
                "-R",
                requirement,
                installed,
            )
            run("xcrun", "stapler", "validate", installed)
            run("syspolicy_check", "distribution", installed)
            run("spctl", "--assess", "--type", "execute", "-vv", installed)
        run(
            "bash",
            Path(__file__).with_name("smoke.sh"),
            tmp / "Crewden.app",
            manifest["sha256"],
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    signer = commands.add_parser("sign")
    signer.add_argument("candidate", type=Path)
    signer.add_argument("target", type=Path)
    verifier = commands.add_parser("verify")
    verifier.add_argument("directory", type=Path)
    verifier.add_argument(
        "--unsigned-test",
        action="store_true",
        help="Skip Apple trust checks for an internal test artifact",
    )
    args = parser.parse_args()
    if args.command == "sign":
        sign_candidate(
            args.candidate,
            args.target,
            os.environ.get("MACOS_SIGNING_IDENTITY", ""),
            os.environ.get("MACOS_NOTARY_PROFILE", ""),
        )
    else:
        verify(args.directory, args.unsigned_test, os.environ.get("MACOS_TEAM_ID", ""))


if __name__ == "__main__":
    main()
