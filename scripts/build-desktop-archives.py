#!/usr/bin/env python3
"""Build split runtime + app (+ frontend/trajectory UI) archives for Crewden Desktop.

Always fetches and SHA-256 verifies official Node.js v24.22.1 distribution binaries
from nodejs.org (never copying whatever `node` happens to be on the build host's PATH).
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.parse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "node_modules/.pnpm"
NODE_VERSION = "24.22.1"
NODE_DIST_BASE = f"https://nodejs.org/dist/v{NODE_VERSION}"

ALTERNATE_CLI_PACKAGES = {
    "@deepseek-ai/dsh-acp-app",
    "@deepseek-ai/dsh-client-ui-agent-preset",
    "@deepseek-ai/dsh-client-ui-cordis",
    "@deepseek-ai/dsh-cordis-client-runner",
    "@deepseek-ai/dsh-cua-bundle",
    "@deepseek-ai/dsh-deepseek-chat-import",
    "@deepseek-ai/dsh-experimental-auto-review",
    "@deepseek-ai/dsh-experimental-badge-skill-bundle",
    "@deepseek-ai/dsh-experimental-cot-translation-bundle",
    "@deepseek-ai/dsh-experimental-forge-bundle",
    "@deepseek-ai/dsh-experimental-inspector-profile",
    "@deepseek-ai/dsh-experimental-liveshare",
    "@deepseek-ai/dsh-experimental-plugin-market-bundle",
    "@deepseek-ai/dsh-experimental-ralph-bundle",
    "@deepseek-ai/dsh-experimental-session-search",
    "@deepseek-ai/dsh-experimental-session-titles-bundle",
    "@deepseek-ai/dsh-experimental-terminal-bundle",
    "@deepseek-ai/dsh-experimental-tool-worktree",
    "@deepseek-ai/dsh-experimental-voice-input-bundle",
    "@deepseek-ai/dsh-headless",
    "@deepseek-ai/dsh-personalized-recommendations",
    "@deepseek-ai/dsh-sdk-app",
    "@deepseek-ai/dsh-sdk-minimal",
    "@deepseek-ai/dsh-skill-office",
    "@deepseek-ai/dsh-web-app",
}

PLATFORM_CONFIG = {
    "desktop-darwin-arm64": {
        "node_archive": f"node-v{NODE_VERSION}-darwin-arm64.tar.gz",
        "node_subdir": f"node-v{NODE_VERSION}-darwin-arm64",
        "installer_name": "Crewden-Desktop-arm64.dmg",
        "descriptor_name": "desktop-darwin-arm64.json",
        "manifest_name": "manifest.desktop-darwin-arm64.json",
        "runtime_archive": "desktop-runtime-darwin-arm64.tar.gz",
        "app_archive": "desktop-app-darwin-arm64.tar.gz",
        "foreign_parts": {
            "linux-x64",
            "linux-arm64",
            "darwin-x64",
            "win32-x64",
            "win32-arm64",
            "win10-x64",
            "win10-arm64",
        },
    },
    "desktop-win32-x64": {
        "node_archive": f"node-v{NODE_VERSION}-win-x64.zip",
        "node_subdir": f"node-v{NODE_VERSION}-win-x64",
        "installer_name": "Crewden-Desktop-Setup-x64.exe",
        "descriptor_name": "desktop-win32-x64.json",
        "manifest_name": "manifest.desktop-win32-x64.json",
        "runtime_archive": "desktop-runtime-win32-x64.tar.gz",
        "app_archive": "desktop-app-win32-x64.tar.gz",
        "foreign_parts": {
            "linux-x64",
            "linux-arm64",
            "darwin-x64",
            "darwin-arm64",
            "win32-arm64",
            "win10-arm64",
        },
    },
}


def encoded(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def digest_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def normalize_commit_sha(raw_commit: str, repo_root: Path = ROOT) -> str:
    """Resolve any git revision or short SHA to a canonical 40-char lowercase commit SHA.

    Args:
      raw_commit: User-supplied commit ref/SHA, or empty string for `HEAD`.
      repo_root: Git repository root used for `git rev-parse`.

    Returns:
      Verified 40-character lowercase hexadecimal commit SHA.
    """
    target = raw_commit.strip() or "HEAD"
    try:
        resolved = (
            subprocess.check_output(
                ["git", "rev-parse", "--verify", f"{target}^{{commit}}"],
                cwd=repo_root,
                text=True,
                stderr=subprocess.PIPE,
            )
            .strip()
            .lower()
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"Invalid --source-commit '{raw_commit}': {exc.stderr.strip() or 'not a valid git commit'}"
        ) from exc
    if not re.fullmatch(r"[a-f0-9]{40}", resolved):
        raise ValueError(
            f"Resolved commit '{resolved}' is not a 40-character lowercase hex SHA"
        )
    return resolved


def classify_origin_security(raw_url: str) -> tuple[str, str | None]:
    """Classify an HTTP(S) URL origin using strict literal IP parsing and reserved-domain rules.

    Args:
      raw_url: Candidate URL or origin string.

    Returns:
      Tuple `(kind, normalized_origin)` where `kind` is one of `'https'`, `'loopback_http'`,
      `'private_http'`, `'rejected_public_http'`, or `'invalid'`.
    """
    trimmed = raw_url.strip()
    if not trimmed:
        return "invalid", None
    parsed = urllib.parse.urlsplit(trimmed)
    scheme = parsed.scheme.lower()
    if (
        scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return "invalid", None
    try:
        port = parsed.port
    except ValueError:
        return "invalid", None

    host = parsed.hostname.lower()
    bracketed_host = f"[{host}]" if ":" in host else host
    default_port = 443 if scheme == "https" else 80
    netloc = (
        bracketed_host
        if port is None or port == default_port
        else f"{bracketed_host}:{port}"
    )
    normalized_origin = f"{scheme}://{netloc}"

    if scheme == "https":
        return "https", normalized_origin

    if host == "crewden.work" or host.endswith(".crewden.work"):
        return "rejected_public_http", normalized_origin
    if host == "localhost":
        return "loopback_http", normalized_origin

    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        octets = host.split(".")
        if any(len(part) > 1 and part.startswith("0") for part in octets):
            return "rejected_public_http", normalized_origin
        nums = [int(part) for part in octets]
        if any(n < 0 or n > 255 for n in nums):
            return "rejected_public_http", normalized_origin
        if nums[0] == 127:
            return "loopback_http", normalized_origin
        if (
            nums[0] == 10
            or (nums[0] == 172 and 16 <= nums[1] <= 31)
            or (nums[0] == 192 and nums[1] == 168)
        ):
            return "private_http", normalized_origin
        return "rejected_public_http", normalized_origin

    if ":" in host:
        try:
            ipv6 = ipaddress.IPv6Address(host)
        except ValueError:
            return "invalid", None
        if ipv6.is_loopback:
            return "loopback_http", normalized_origin
        first_word = int(ipv6) >> 112
        if (first_word & 0xFE00) == 0xFC00 or (first_word & 0xFFC0) == 0xFE80:
            return "private_http", normalized_origin
        return "rejected_public_http", normalized_origin

    if (
        host.endswith(".local")
        and len(host) > len(".local")
        and not host.startswith(".")
    ):
        return "private_http", normalized_origin
    return "rejected_public_http", normalized_origin


def normalize_im_origin(raw_origin: str) -> tuple[str, str]:
    """Validate and normalize a preset Desktop IM origin (`scheme://host[:port]`).

    Args:
      raw_origin: Candidate IM origin string.

    Returns:
      Tuple `(normalized_origin, security_kind)`.
    """
    parsed = urllib.parse.urlsplit(raw_origin.strip())
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError(
            f"Invalid --default-im-origin '{raw_origin}': expected scheme://host[:port] without path or query"
        )
    kind, origin = classify_origin_security(raw_origin)
    if kind in ("invalid", "rejected_public_http") or not origin:
        raise ValueError(
            f"Disallowed --default-im-origin '{raw_origin}': official and public domains require https://"
        )
    return origin, kind


def normalize_release_base_url(raw_base: str) -> tuple[str, str]:
    """Validate and normalize a self-hosted release base URL prefix ending with `/`.

    Args:
      raw_base: Candidate release base URL prefix.

    Returns:
      Tuple `(normalized_base_with_slash, security_kind)`.
    """
    parsed = urllib.parse.urlsplit(raw_base.strip())
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError(
            f"Invalid --base-url '{raw_base}': query, fragment, and userinfo are not allowed"
        )
    kind, origin = classify_origin_security(raw_base)
    if kind in ("invalid", "rejected_public_http") or not origin:
        raise ValueError(
            f"Disallowed --base-url '{raw_base}': official and public domains require https://"
        )
    clean_path = parsed.path.rstrip("/")
    return f"{origin}{clean_path}/", kind


def _version_sort_key(version: str) -> tuple[tuple[int, int | str], ...]:
    tokens: list[tuple[int, int | str]] = []
    for part in re.split(r"([0-9]+)", version):
        if not part:
            continue
        if part.isdigit():
            tokens.append((1, int(part)))
        else:
            tokens.append((0, part))
    return tuple(tokens)


def download_url_to_file(url: str, dest: Path) -> None:
    """Download with curl range-resume loop (handles partial transfers cleanly across macOS/Linux/Windows)."""
    part = dest.with_name(dest.name + ".part")
    curl_bin = "curl.exe" if os.name == "nt" else "curl"
    last_err: Exception | None = None
    for attempt in range(8):
        res = subprocess.run(
            [
                curl_bin,
                "--http1.1",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "-C",
                "-",
                url,
                "-o",
                str(part),
            ]
        )
        if res.returncode == 0:
            part.replace(dest)
            return
        if res.returncode == 33:
            # Server rejected range or file already complete/corrupt -> restart clean once
            part.unlink(missing_ok=True)
        last_err = RuntimeError(
            f"curl exited with {res.returncode} on attempt {attempt + 1} for {url}"
        )
    raise last_err or RuntimeError(f"Failed to download {url}")


def ensure_official_node(platform: str, cache_dir: Path) -> Path:
    """Download and SHA-256 verify official Node.js v24.22.1 for the target platform."""
    cfg = PLATFORM_CONFIG[platform]
    archive_name = cfg["node_archive"]
    extracted_root = cache_dir / cfg["node_subdir"]
    marker = extracted_root / ".verified-sha256"
    cache_dir.mkdir(parents=True, exist_ok=True)

    shasums_path = cache_dir / f"SHASUMS256-v{NODE_VERSION}.txt"
    if not shasums_path.is_file():
        download_url_to_file(f"{NODE_DIST_BASE}/SHASUMS256.txt", shasums_path)

    expected_sha = None
    for line in shasums_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == archive_name:
            expected_sha = parts[0]
            break
    if not expected_sha:
        raise RuntimeError(f"Could not find {archive_name} in official SHASUMS256.txt")

    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == expected_sha:
        return extracted_root

    archive_path = cache_dir / archive_name
    if not archive_path.is_file() or digest_file(archive_path) != expected_sha:
        archive_path.unlink(missing_ok=True)
        download_url_to_file(f"{NODE_DIST_BASE}/{archive_name}", archive_path)
        actual_sha = digest_file(archive_path)
        if actual_sha != expected_sha:
            archive_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"SHA-256 mismatch for {archive_name}: {actual_sha} != {expected_sha}"
            )

    if extracted_root.exists():
        shutil.rmtree(extracted_root)
    if archive_name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(cache_dir)
    else:
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(cache_dir)
    marker.write_text(expected_sha + "\n", encoding="utf-8")
    return extracted_root


def ensure_locked_pnpm(cache_dir: Path) -> Path:
    """Fetch the locked pnpm@11.7.0 package tarball for self-contained runtime tooling."""
    pnpm_root = cache_dir / "pnpm-11.7.0" / "package"
    if (pnpm_root / "bin/pnpm.cjs").is_file():
        return pnpm_root
    tgz = cache_dir / "pnpm-11.7.0.tgz"
    if not tgz.is_file():
        download_url_to_file("https://registry.npmjs.org/pnpm/-/pnpm-11.7.0.tgz", tgz)
    dest = cache_dir / "pnpm-11.7.0"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgz, "r:gz") as tar:
        tar.extractall(dest)
    return pnpm_root


def collect_files(source: Path, prefix: str, foreign_parts: set[str]):
    symbols = (
        ".pdb",
        ".d.ts",
        ".d.cts",
        ".d.mts",
        ".js.map",
        ".mjs.map",
        ".cjs.map",
        ".ts.map",
        ".mts.map",
        ".cts.map",
        ".css.map",
    )
    for directory, dirs, entries in os.walk(source):
        dirs[:] = [d for d in dirs if d != ".bin"]
        for name in entries:
            path = Path(directory) / name
            relative = path.relative_to(source)
            if any(part in foreign_parts for part in relative.parts):
                continue
            if path.is_file() and not name.lower().endswith(symbols):
                yield f"{prefix}/{relative.as_posix()}", path


def dependencies(directory: Path):
    for entry in sorted(directory.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.name.startswith("@"):
            yield from (
                (f"{entry.name}/{child.name}", child)
                for child in sorted(entry.iterdir())
            )
        else:
            yield entry.name, entry


def store_path(package: Path) -> str:
    key = package.relative_to(STORE).as_posix()
    return "p/" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def build_graph(foreign_parts: set[str]):
    app, runtime, local_links, external_links, groups = {}, {}, {}, {}, {}
    visited = set()
    store_candidates: dict[str, list[tuple[str, str]]] = {}
    dsh_web_prefixes: list[str] = []
    pending = [ROOT / "apps/node"]
    while pending:
        package = pending.pop().resolve()
        if package in visited:
            continue
        visited.add(package)
        info = json.loads((package / "package.json").read_text(encoding="utf-8"))
        if package.is_relative_to(STORE):
            prefix = store_path(package)
            pkg_name = str(info["name"])
            pkg_ver = str(info["version"])
            groups[prefix] = f"{pkg_name}@{pkg_ver}"
            store_candidates.setdefault(pkg_name, []).append((pkg_ver, prefix))
            if pkg_name == "@deepseek-ai/dsh-web":
                dsh_web_prefixes.append(prefix)
            runtime.update(collect_files(package, prefix, foreign_parts))
            modules = STORE / package.relative_to(STORE).parts[0] / "node_modules"
            for name, link in dependencies(modules):
                target = link.resolve()
                if pkg_name == "@deepseek-ai/dsh" and name in ALTERNATE_CLI_PACKAGES:
                    continue
                if target == package:
                    continue
                external_links[f"{prefix}/node_modules/{name}"] = store_path(target)
                pending.append(target)
        else:
            prefix = package.relative_to(ROOT).as_posix()
            app[f"{prefix}/package.json"] = package / "package.json"
            app.update(collect_files(package / "lib", f"{prefix}/lib", foreign_parts))
            for name in info.get("dependencies", {}):
                target = (package / "node_modules" / name).resolve(strict=True)
                local_links[f"{prefix}/node_modules/{name}"] = (
                    "runtime/" + store_path(target)
                    if target.is_relative_to(STORE)
                    else target.relative_to(ROOT).as_posix()
                )
                pending.append(target)
    for name, link in dependencies(STORE / "node_modules"):
        target = link.resolve()
        if target in visited and target.is_relative_to(STORE):
            external_links["p/node_modules/" + name] = store_path(target)
    # Multi-version lockfile packages may hoist a non-visited variant at `.pnpm/node_modules/<name>`.
    # Provide a deterministic fallback link in `p/node_modules/<name>` for every visited package.
    for pkg_name, candidates in sorted(store_candidates.items()):
        hoist_key = "p/node_modules/" + pkg_name
        if hoist_key not in external_links:
            best_ver, best_prefix = max(
                candidates, key=lambda item: (_version_sort_key(item[0]), item[1])
            )
            _ = best_ver
            external_links[hoist_key] = best_prefix
    zod_target = external_links.get("p/node_modules/zod")
    if zod_target:
        for dsh_web_prefix in dsh_web_prefixes:
            external_links.setdefault(f"{dsh_web_prefix}/node_modules/zod", zod_target)
    runtime["dependencies.json"] = encoded(external_links)
    app["workspaces.json"] = encoded(local_links)
    return app, runtime, groups


def write_tar_gz(
    out_dir: Path, name: str, entries: dict[str, Path | bytes]
) -> dict[str, object]:
    out_path = out_dir / name
    with gzip_deterministic(out_path) as gz_stream:
        with tarfile.open(fileobj=gz_stream, mode="w") as tar:
            for relative, source in sorted(entries.items()):
                info = tarfile.TarInfo(name=relative)
                info.mtime = 946684800
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                if isinstance(source, bytes):
                    info.size = len(source)
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(source))
                else:
                    stat = source.stat()
                    is_exec = bool(stat.st_mode & 0o111) or relative.endswith(
                        (".exe", "bin/node", "spawn-helper")
                    )
                    info.size = stat.st_size
                    info.mode = 0o755 if is_exec else 0o644
                    with source.open("rb") as reader:
                        tar.addfile(info, reader)
    return {
        "name": name,
        "size": out_path.stat().st_size,
        "sha256": digest_file(out_path),
    }


class gzip_deterministic:
    """Context manager producing deterministic gzip output (mtime=0)."""

    def __init__(self, path: Path):
        self.path = path
        self.raw = None
        self.gz = None

    def __enter__(self):
        import gzip

        self.raw = self.path.open("wb")
        self.gz = gzip.GzipFile(
            filename="", mode="wb", fileobj=self.raw, compresslevel=6, mtime=0
        )
        return self.gz

    def __exit__(self, exc_type, exc, tb):
        if self.gz is not None:
            self.gz.close()
        if self.raw is not None:
            self.raw.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=sorted(PLATFORM_CONFIG), required=True)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist/desktop-release")
    parser.add_argument(
        "--installer",
        type=Path,
        default=None,
        help="Built DMG or Setup.exe installer path (optional when building embedded seed archives)",
    )
    parser.add_argument("--version", default=os.environ.get("RELEASE_VERSION", ""))
    parser.add_argument("--source-commit", default="")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("IM_RELEASE_BASE_URL", ""),
        help="Trusted self-hosted release base URL prefix",
    )
    parser.add_argument(
        "--default-im-origin",
        default=os.environ.get("CREWDEN_DEFAULT_IM_ORIGIN", ""),
        help="Optional preset default IM origin written to desktop-defaults.json",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=ROOT / ".cache/desktop-archives"
    )
    parser.add_argument(
        "--extra-app-note",
        default="",
        help="Optional marker file content in app archive for update tests",
    )
    args = parser.parse_args()

    cfg = PLATFORM_CONFIG[args.platform]
    commit = normalize_commit_sha(args.source_commit, ROOT)
    version = args.version.strip() or commit
    tag = f"node-{commit}" if version == commit else f"v{version}"

    custom_base_url: str | None = None
    allow_private_http_base = False
    if args.base_url.strip():
        normalized_base, base_kind = normalize_release_base_url(args.base_url)
        custom_base_url = normalized_base
        allow_private_http_base = base_kind == "private_http"

    preset_im_origin: str | None = None
    if args.default_im_origin.strip():
        preset_im_origin, _origin_kind = normalize_im_origin(args.default_im_origin)

    metadata: dict[str, object] = {
        "source_commit": commit,
        "updater_protocol": 1,
        "data_epoch": 1,
        "shell_protocol": 2,
    }
    nano_release_meta: dict[str, object] = dict(metadata)
    if custom_base_url is not None:
        nano_release_meta["trusted_release_base_url"] = custom_base_url
        nano_release_meta["allow_private_http_release_base"] = allow_private_http_base

    frontend_dist = ROOT / "src/IM/frontend/dist"
    trajectory_dist = ROOT / "packages/dsh-trajectory-viewer/dist"
    if not (frontend_dist / "index.html").is_file():
        raise RuntimeError(
            f"Missing frontend dist at {frontend_dist}; build frontend first"
        )
    if not (trajectory_dist / "index.html").is_file():
        raise RuntimeError(
            f"Missing trajectory viewer dist at {trajectory_dist}; build trajectory viewer first"
        )

    node_root = ensure_official_node(args.platform, args.cache_dir)
    pnpm_root = ensure_locked_pnpm(args.cache_dir)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    foreign_parts = set(cfg["foreign_parts"])

    app, runtime, _groups = build_graph(foreign_parts)
    for tracked in (
        subprocess.check_output(
            [
                "git",
                "ls-files",
                "-z",
                "--",
                "packages/dsh-integration/assets",
                "packages/dsh-integration/cordis.patch.yml",
                "packages/personal-assistant/assets",
            ],
            cwd=ROOT,
        )
        .decode("utf-8")
        .split("\0")
    ):
        if tracked:
            app[tracked] = ROOT / tracked

    app["package.json"] = ROOT / "package.json"
    app[".nano-release.json"] = encoded(nano_release_meta)
    app.update(collect_files(frontend_dist, "ui/frontend", set()))
    app.update(collect_files(trajectory_dist, "ui/trajectory", set()))
    if args.extra_app_note:
        app["ui/frontend/build-note.txt"] = args.extra_app_note.encode("utf-8")

    if "apps/node/lib/cli.js" not in app:
        raise RuntimeError(
            "Build the Node workspace (`pnpm build`) before creating desktop archives"
        )

    if args.platform == "desktop-darwin-arm64":
        runtime["bin/node"] = node_root / "bin/node"
        runtime["NODE-LICENSE"] = node_root / "LICENSE"
    else:
        runtime["node.exe"] = node_root / "node.exe"
        runtime["NODE-LICENSE"] = node_root / "LICENSE"
        desktop_host_exe = ROOT / "dist/desktop-windows-build/DesktopGatewayHost.exe"
        if desktop_host_exe.is_file():
            app["apps/node/lib/DesktopGatewayHost.exe"] = desktop_host_exe

    runtime["layout.mjs"] = ROOT / "packaging/desktop/layout.mjs"
    runtime.update(collect_files(pnpm_root, "tooling/node_modules/pnpm", foreign_parts))

    base = (
        custom_base_url
        if custom_base_url is not None
        else f"https://github.com/Mrchen116/nano-multiagent/releases/download/{tag}/"
    )

    runtime_info = write_tar_gz(out_dir, cfg["runtime_archive"], runtime)
    app_info = write_tar_gz(out_dir, cfg["app_archive"], app)

    installer_name = str(cfg["installer_name"])
    if args.installer is not None:
        if not args.installer.is_file() or args.installer.stat().st_size <= 0:
            raise ValueError(
                f"--installer '{args.installer}' must exist and have non-zero size"
            )
        installer_dest = out_dir / installer_name
        if args.installer.resolve() != installer_dest.resolve():
            shutil.copy2(args.installer, installer_dest)
        installer_size = installer_dest.stat().st_size
        installer_sha256 = digest_file(installer_dest)
    else:
        installer_size = 1
        installer_sha256 = "0" * 64

    descriptor = {
        "version": version,
        **metadata,
        "runtime": {**runtime_info, "download_url": base + str(runtime_info["name"])},
        "app": {**app_info, "download_url": base + str(app_info["name"])},
    }
    descriptor_path = out_dir / cfg["descriptor_name"]
    descriptor_path.write_bytes(encoded(descriptor))

    manifest: dict[str, object] = {
        "version": version,
        **metadata,
        **(
            {"release_base_url": custom_base_url} if custom_base_url is not None else {}
        ),
        "package": descriptor_path.name,
        "platform": args.platform,
        "node_major": 24,
        "pnpm_version": "11.7.0",
        "size": descriptor_path.stat().st_size,
        "sha256": digest_file(descriptor_path),
        "download_url": base + descriptor_path.name,
        "installer": {
            "download_url": base + installer_name,
            "size": installer_size,
            "sha256": installer_sha256,
        },
    }
    manifest_path = out_dir / cfg["manifest_name"]
    manifest_path.write_bytes(encoded(manifest))

    defaults_path = out_dir / "desktop-defaults.json"
    if preset_im_origin is not None or custom_base_url is not None:
        desktop_defaults: dict[str, object] = {}
        if preset_im_origin is not None:
            desktop_defaults["default_im_origin"] = preset_im_origin
        if custom_base_url is not None:
            desktop_defaults["trusted_release_base_url"] = custom_base_url
            desktop_defaults["allow_private_http_release_base"] = (
                allow_private_http_base
            )
        defaults_path.write_bytes(encoded(desktop_defaults))
    else:
        defaults_path.unlink(missing_ok=True)

    print(
        json.dumps(
            {
                "platform": args.platform,
                "version": version,
                "node_version": NODE_VERSION,
                "installer_bytes": installer_size,
                "runtime_bytes": runtime_info["size"],
                "runtime_sha256": runtime_info["sha256"],
                "app_bytes": app_info["size"],
                "app_sha256": app_info["sha256"],
                "descriptor_sha256": manifest["sha256"],
                "manifest_path": str(manifest_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
