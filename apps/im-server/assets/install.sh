#!/usr/bin/env bash
set -euo pipefail
umask 077
NANO_ORIGIN=__NANO_ORIGIN__
NANO_ROOT="${NANO_INSTALL_ROOT:-$HOME/.nanoassistant}"
mkdir -p "$NANO_ROOT/downloads" "$NANO_ROOT/releases" "$NANO_ROOT/tooling"
NANO_TEMP=$(mktemp -d "$NANO_ROOT/downloads/install.XXXXXX")
trap 'rm -rf "$NANO_TEMP"' EXIT
trap 'echo "Installation paused. Your files are preserved. Run the same command to continue." >&2' ERR
hash_file() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}';
  else sha256sum "$1" | awk '{print $1}'; fi
}
fetch() { curl --fail --location --silent --show-error --retry 2 "$1" -o "$2"; }
echo '1/4 Preparing the computer runtime…'
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 && node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>=24||a===22&&b>=19?0:1)'; then
  NANO_NODE=$(command -v node)
else
  case "$(uname -s)" in Darwin) NANO_OS=darwin;; Linux) NANO_OS=linux;; *) echo 'Use macOS, Linux, or WSL on Windows.' >&2; exit 1;; esac
  case "$(uname -m)" in arm64|aarch64) NANO_ARCH=arm64;; x86_64|amd64) NANO_ARCH=x64;; *) echo 'Supported computers: arm64 or x64.' >&2; exit 1;; esac
  fetch 'https://nodejs.org/dist/latest-v24.x/SHASUMS256.txt' "$NANO_TEMP/node-sums"
  NANO_NODE_ARCHIVE=$(awk -v suffix="-$NANO_OS-$NANO_ARCH.tar.gz" 'substr($2,length($2)-length(suffix)+1)==suffix {print $2;exit}' "$NANO_TEMP/node-sums")
  test -n "$NANO_NODE_ARCHIVE"
  fetch "https://nodejs.org/dist/latest-v24.x/$NANO_NODE_ARCHIVE" "$NANO_TEMP/node.tgz"
  NANO_EXPECTED=$(awk -v file="$NANO_NODE_ARCHIVE" '$2==file {print $1}' "$NANO_TEMP/node-sums")
  test "$(hash_file "$NANO_TEMP/node.tgz")" = "$NANO_EXPECTED"
  NANO_NODE_DIR="$NANO_ROOT/tooling/${NANO_NODE_ARCHIVE%.tar.gz}"
  if [ ! -x "$NANO_NODE_DIR/bin/node" ]; then
    tar -xzf "$NANO_TEMP/node.tgz" -C "$NANO_ROOT/tooling"
  fi
  NANO_NODE="$NANO_NODE_DIR/bin/node"
fi
export PATH="$(dirname "$NANO_NODE"):$PATH"
if [ ! -f "$NANO_ROOT/tooling/node_modules/pnpm/bin/pnpm.cjs" ]; then
  npm install --prefix "$NANO_ROOT/tooling" --no-audit --no-fund pnpm@11.7.0
fi
NANO_PNPM="$NANO_ROOT/tooling/node_modules/pnpm/bin/pnpm.cjs"
echo '2/4 Downloading Nano from your IM service…'
fetch "$NANO_ORIGIN/install/manifest.json" "$NANO_TEMP/manifest.json"
NANO_HASH=$("$NANO_NODE" -e 'const fs=require("fs");const x=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));if(!/^[a-f0-9]{64}$/.test(x.sha256))process.exit(1);console.log(x.sha256)' "$NANO_TEMP/manifest.json")
NANO_RELEASE="$NANO_ROOT/releases/$NANO_HASH"
if [ ! -f "$NANO_RELEASE/.installed" ]; then
  fetch "$NANO_ORIGIN/install/nano-node.tgz" "$NANO_TEMP/nano-node.tgz"
  if [ "$(hash_file "$NANO_TEMP/nano-node.tgz")" != "$NANO_HASH" ]; then
    echo 'Download verification failed. Please run the command again.' >&2; exit 1
  fi
  mkdir -p "$NANO_TEMP/package"
  tar -xzf "$NANO_TEMP/nano-node.tgz" -C "$NANO_TEMP/package"
  echo '3/4 Installing dependencies in your private Nano folder…'
  (cd "$NANO_TEMP/package" && "$NANO_NODE" "$NANO_PNPM" install --prod --frozen-lockfile)
  touch "$NANO_TEMP/package/.installed"
  # Reuse only complete installations; a failed attempt never replaces a running version.
  if [ ! -e "$NANO_RELEASE" ]; then mv "$NANO_TEMP/package" "$NANO_RELEASE"; fi
fi
echo '4/4 Confirm this computer in your browser…'
"$NANO_NODE" "$NANO_RELEASE/apps/node/lib/cli.js" setup --im-service-url "$NANO_ORIGIN"
echo 'Your computer is connected. Return to Nano to choose a model and create your assistant.'
