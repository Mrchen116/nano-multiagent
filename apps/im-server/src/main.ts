import { parseArgs } from "node:util";
import { createServer, resolveSecret } from "./server.js";
import { openDatabase } from "./db.js";
import { createIdentity } from "./identity.js";
const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    host: { type: "string" },
    port: { type: "string" },
    db: { type: "string" },
    "db-path": { type: "string" },
    username: { type: "string" },
    password: { type: "string" },
    "display-name": { type: "string" },
    locale: { type: "string" },
    "node-id": { type: "string" },
    "public-key": { type: "string" },
    "key-id": { type: "string" },
  },
});
async function main() {
  const command = positionals[0] ?? "serve";
  if (["init-admin", "init_admin", "enroll-device", "enroll_device"].includes(command)) {
    const db = openDatabase(
      values.db ?? values["db-path"] ?? process.env.IM_DB_PATH ?? "data/im_service.sqlite3",
    );
    try {
      const identity = createIdentity(db, resolveSecret());
      if (command === "init-admin" || command === "init_admin") {
        if (!values.username || !values.password || !values["display-name"])
          throw Error("--username, --password and --display-name required");
        const pair = await identity.register(
          values.username,
          values.password,
          values["display-name"],
          values.locale ?? "en",
        );
        identity.initializeCompany(pair.user.id);
        console.log(`init_admin: created user ${pair.user.id} (owner_id=${pair.user.owner_id})`);
      } else {
        if (!values["node-id"] || !values["public-key"] || !values["key-id"])
          throw Error("--node-id, --public-key and --key-id required");
        identity.enrollDevice(values["node-id"], values["public-key"], values["key-id"]);
        console.log("Device public key enrolled. Run Gateway --recover-device locally.");
      }
    } finally {
      db.close();
    }
    return;
  }
  if (command === "public-server" || command === "public_server") {
    if (!process.env.IM_PUBLIC_URL?.startsWith("https://"))
      throw Error("IM_PUBLIC_URL must name the public HTTPS origin");
    process.env.IM_PUBLIC_MODE = "1";
    process.env.IM_TRUSTED_PROXY = "127.0.0.1";
  } else if (command !== "serve") throw Error("unknown command");
  const app = await createServer({ dbPath: values.db ?? values["db-path"] });
  await app.listen({
    host: command.startsWith("public") ? "127.0.0.1" : (values.host ?? "127.0.0.1"),
    port: Number(values.port ?? process.env.IM_PORT ?? 8011),
  });
  console.log(
    `IM listening on ${app.server.address() && typeof app.server.address() === "object" ? (app.server.address() as any).port : ""}`,
  );
  for (const signal of ["SIGINT", "SIGTERM"])
    process.once(signal, () => {
      void app.close().then(() => process.exit(0));
    });
}
main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
