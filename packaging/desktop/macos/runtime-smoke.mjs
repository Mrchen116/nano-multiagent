// Exercise the installed node's default DSH profile and its native plugin loader.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [versionRoot, home] = process.argv.slice(2);
const require = createRequire(join(versionRoot, "apps/node/lib/cli.js"));
const { prepareProfile, RuntimeClient } = await import(pathToFileURL(require.resolve("@nano/dsh-integration/client")));
await prepareProfile(home);
const client = new RuntimeClient({ home, cwd: home, onLog: text => process.stderr.write(text) });
const timeout = setTimeout(() => client.process.kill("SIGKILL"), 90_000);
try {
  await client.rpc.request("initialize", { protocol: 1, agents: [], bindings: [], providers: {} });
  assert.equal((await client.rpc.request("runtime.health", {})).healthy, true);
  console.log("Packaged DSH profile initialized and runtime.health succeeded");
  await client.shutdown();
} finally {
  clearTimeout(timeout);
  if (client.process.exitCode === null && client.process.signalCode === null) {
    client.process.kill("SIGKILL");
  }
}
