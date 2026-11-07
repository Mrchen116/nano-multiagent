#!/usr/bin/env bash
set -euo pipefail
umask 077
repo="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$repo"
run="$(cd "$1" && pwd)"
patch="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
python3 "$repo/scripts/dev_host.py" guard --repo "$repo" --runtime "$run" --profile default
if [[ -f "$run/provider.json" ]]; then
  echo "Use a fresh run directory" >&2
  exit 1
fi
python3 - "$run" "$patch" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

run, patch = map(Path, sys.argv[1:])
prompt = Path("packages/dsh-integration/src/global-mode.ts")
skill = Path("packages/personal-assistant/assets/skills/nano-ongoing-work/SKILL.md")
def section(path):
    return re.search(r'`(You are the long-lived Agent.*?)`', path.read_text(), re.S).group(1)
def body(path):
    return path.read_text().split("---", 2)[2].strip()
with tempfile.TemporaryDirectory(dir=run) as temp:
    temp = Path(temp)
    for path in (prompt, skill):
        (temp / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, temp / path)
    subprocess.run(["git", "apply", "--no-index", str(patch)], cwd=temp, check=True)
    versions = [(section(prompt), section(temp / prompt)), (body(skill), body(temp / skill))]
    assert all(a != b for a, b in versions)
    result = {
        "base": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "patchSha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        "replacements": versions,
    }
    (run / "variants.json").write_text(json.dumps(result, ensure_ascii=False))
PY
provider_pid="$(node --input-type=module - "$repo/evals/agent_coordination/provider.mjs" "$run" <<'JS'
import { spawn } from 'node:child_process';
import { openSync } from 'node:fs';
const [script, run] = process.argv.slice(2);
const log = openSync(run + '/provider.log', 'a');
const child = spawn(process.execPath, [script, run], { detached: true, stdio: ['ignore', log, log] });
child.unref();
console.log(child.pid);
JS
)"
trap 'kill "$provider_pid" 2>/dev/null || true; "$repo/scripts/e2e-down.sh" --wt "$run" >/dev/null 2>&1 || true' EXIT
for _ in {1..50}; do
  if [[ -s "$run/provider.json" ]]; then break; fi
  sleep 0.1
done
python3 - "$run" <<'PY'
import copy
import json
from pathlib import Path
import sys
import yaml
run = Path(sys.argv[1])
source = yaml.safe_load(Path("config/e2e/gateway.yaml").read_text())
provider = source["llm"]["providers"][0]
provider["base_url"] = json.loads((run / "provider.json").read_text())["url"]
provider["models"] = [m for m in provider["models"] if m["name"] == "codexOAuth:gpt-6.1-sol"]
source["llm"] = {"default_model": "codexOAuth:gpt-6.1-sol", "providers": [provider]}
template = next(a for a in source["agents"] if a["agent_id"] == "e2e-global")
source["agents"] = []
for arm in ("a", "b"):
    agent = copy.deepcopy(template)
    agent.update(
        agent_id="coord-" + arm, title="Coord " + arm.upper(),
        custom_prompt="你长期负责这个项目。可以分派独立任务，用已明确的要求回答子 Agent。影响产品范围且现有授权未覆盖时问用户。",
        default_model="codexOAuth:gpt-6.1-sol", reasoning_effort="high",
    )
    source["agents"].append(agent)
(run / "config.yaml").write_text(yaml.safe_dump(source, allow_unicode=True))
PY
revision="$(git rev-parse HEAD)"
for arm in a b; do
  workspace="$run/.gateway-workspace/coord-$arm"
  mkdir -p "$workspace"
  git archive "$revision" -- . ':(exclude)evals' | tar -xf - -C "$workspace"
  git -C "$workspace" init -q
  git -C "$workspace" add -A
  git -C "$workspace" -c user.name='Nano eval snapshot' -c user.email=eval@localhost \
    -c commit.gpgsign=false commit -qm "Nano source snapshot $revision"
done
"$repo/scripts/e2e-up.sh" --wt "$run" --main-config "$run/config.yaml"
node "$repo/evals/agent_coordination/defaults.mjs" "$run"
trap - EXIT
