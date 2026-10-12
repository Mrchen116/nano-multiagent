import {
  mkdtemp,
  writeFile,
  readFile,
  readdir,
  rm,
  mkdir,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:http";
import {
  createPublicKey,
  generateKeyPairSync,
  diffieHellman,
  hkdfSync,
  randomBytes,
  createCipheriv,
  createHmac,
  createHash,
} from "node:crypto";
import { expect, it } from "vitest";
import { bindDevice } from "../src/device-binding.js";
import { NodeConfiguration } from "../src/configuration.js";
const canonical = (value: object) =>
  JSON.stringify(
    Object.fromEntries(
      Object.entries(value).sort(([a], [b]) => a.localeCompare(b)),
    ),
  );
it("recovers a committed binding after a lost response and preserves the prior owner runtime", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-device-binding-"));
  const path = join(home, "config.yaml");
  const runtime = join(home, ".dsh-runtime/device");
  const challenge = "private-challenge";
  const confirmation = {
    operation_id: "op",
    target_user_id: "new-user",
    epoch: 1,
    snapshot_hash: "hash",
  };
  const snapshot = {
    agent_profiles: [],
    channel_manifest_heads: [],
    agent_channels: [],
    agent_channel_removals: [],
  };
  let state = "awaiting_account",
    commits = 0;
  const requests: string[] = [];
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = JSON.parse(Buffer.concat(chunks).toString());
    const action = req.url!.split("/").at(-1)!;
    requests.push(action);
    let result: unknown = { state };
    if (action === "start") {
      const remote = createPublicKey({
        key: {
          kty: "OKP",
          crv: "X25519",
          x: Buffer.from(body.public_key, "base64").toString("base64url"),
        },
        format: "jwk",
      });
      const pair = generateKeyPairSync("x25519");
      const salt = randomBytes(32),
        nonce = randomBytes(12),
        aad = { purpose: "device-binding", operation_id: "op" };
      const key = Buffer.from(
        hkdfSync(
          "sha256",
          diffieHellman({ privateKey: pair.privateKey, publicKey: remote }),
          salt,
          "nano-multiagent/device-binding-v1",
          32,
        ),
      );
      const cipher = createCipheriv("aes-256-gcm", key, nonce);
      cipher.setAAD(Buffer.from(canonical(aad)));
      const ciphertext = Buffer.concat([
        cipher.update(challenge),
        cipher.final(),
        cipher.getAuthTag(),
      ]);
      result = {
        operation_id: "op",
        operation_token: "op-token",
        browser_token: "browser-token",
        bind_url: "http://example.invalid",
        challenge: {
          aad,
          ephemeral_public_key: Buffer.from(
            pair.publicKey.export({ format: "jwk" }).x!,
            "base64url",
          ).toString("base64"),
          salt: salt.toString("base64"),
          nonce: nonce.toString("base64"),
          ciphertext: ciphertext.toString("base64"),
        },
      };
    } else if (action === "prove") {
      expect(body.challenge).toBe(challenge);
    } else if (action === "accept") {
      expect(req.headers.authorization).toBe("Bearer browser-access");
      state = "awaiting_local_confirmation";
    } else if (action === "prepare") {
      result = {
        state,
        target_name: "New owner",
        target_user_id: "new-user",
        target_owner: "new-owner",
        confirmation,
        snapshot,
      };
    } else if (action === "commit") {
      expect(body.proof).toBe(
        createHmac("sha256", createHash("sha256").update(challenge).digest())
          .update(canonical(confirmation))
          .digest("hex"),
      );
      state = "committed";
      commits++;
      req.socket.destroy();
      return;
    } else if (action === "recover")
      result = {
        node_id: "device",
        owner_id: "new-owner",
        runtime_token: "runtime-secret",
        snapshot,
      };
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify(result));
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address() as { port: number };
  try {
    await mkdir(runtime, { recursive: true });
    await writeFile(join(runtime, "old-history"), "preserve");
    await writeFile(
      path,
      JSON.stringify({
        node: { node_id: "device", user_id: "old-owner" },
        im_service: {
          url: `http://127.0.0.1:${address.port}`,
          token: "browser-access",
        },
        agents: [],
        llm: { default_model: "x", providers: [] },
      }),
    );
    const config = await NodeConfiguration.read(path);
    const options = {
      auto: true,
      signal: new AbortController().signal,
      confirm: async () => true,
      open: () => {},
      report: () => {},
    };
    await expect(bindDevice(config, options)).rejects.toThrow();
    expect(
      JSON.parse(
        await readFile(join(home, "device-binding-operation.json"), "utf8"),
      ).operation_id,
    ).toBe("op");
    expect(await bindDevice(config, options)).toEqual({
      nodeId: "device",
      ownerId: "new-owner",
    });
    expect(await readdir(runtime)).not.toContain("channels.sqlite3");
    expect(commits).toBe(1);
    expect(requests.filter((action) => action === "start")).toHaveLength(1);
    const archive = (await readdir(join(home, ".dsh-runtime"))).find((name) =>
      name.startsWith("device.previous-owner-"),
    )!;
    expect(
      await readFile(
        join(home, ".dsh-runtime", archive, "old-history"),
        "utf8",
      ),
    ).toBe("preserve");
    expect((await NodeConfiguration.read(path)).value.im_service.token).toBe(
      "runtime-secret",
    );
    await expect(
      readFile(join(home, "device-binding-operation.json")),
    ).rejects.toThrow();
  } finally {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
});
