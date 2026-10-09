#!/usr/bin/env node
import { parseArgs } from "node:util";
import { join, resolve } from "node:path";
import { homedir } from "node:os";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline/promises";
import { NodeConfiguration } from "./configuration.js";
import { manageGateway, applyGatewayEnvironment } from "./lifecycle.js";
import { bindDevice } from "./device-binding.js";
const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    config: { type: "string" },
    foreground: { type: "boolean" },
    "auto-bind": { type: "boolean" },
    "recover-device": { type: "boolean" },
    "im-service-url": { type: "string" },
    help: { type: "boolean", short: "h" },
  },
});
const action = positionals[0] ?? "start";
if (values.help) {
  process.stdout.write(
    "Usage: pnpm pa [start|stop|restart|status|bind] [--config path] [--foreground] [--im-service-url URL] [--auto-bind] [--recover-device]\n",
  );
} else
  try {
    if (!["start", "stop", "restart", "status", "bind"].includes(action))
      throw new Error("Unknown personal-assistant command: " + action);
    const configPath = resolve(
      values.config ?? join(homedir(), ".nanoassistant/config.yaml"),
    );
    const config = await NodeConfiguration.read(configPath);
    if (values["im-service-url"])
      config.value.im_service.url = values["im-service-url"];
    if (
      action === "bind" ||
      values["recover-device"] ||
      (["start", "restart"].includes(action) &&
        (!config.value.node.user_id || !config.value.im_service.token))
    ) {
      if ((await manageGateway(configPath, config.value, "status")).state)
        throw new Error("Stop this node before device binding");
      const abort = new AbortController();
      process.once("SIGINT", () => abort.abort());
      const result = await bindDevice(config, {
        auto:
          values["auto-bind"] || process.env.NANO_MULTIAGENT_AUTO_BIND === "1",
        recover: values["recover-device"],
        signal: abort.signal,
        report: (text) => process.stdout.write(text + "\n"),
        open: (url) => {
          const child = spawn(
            process.platform === "darwin" ? "open" : "xdg-open",
            [url],
            { stdio: "ignore" },
          );
          child.on("error", () => {});
          child.unref();
        },
        confirm: async (text) => {
          const terminal = createInterface({
            input: process.stdin,
            output: process.stdout,
          });
          try {
            return (await terminal.question(text)).trim() === "yes";
          } finally {
            terminal.close();
          }
        },
      });
      process.stdout.write(`Device bound: ${result.nodeId}\n`);
      if (action === "bind") process.exit(0);
    }
    if (values.foreground) {
      if (action !== "start")
        throw new Error("--foreground only applies to start");
      process.argv = [
        process.execPath,
        process.argv[1]!,
        "--config",
        configPath,
        ...(values["im-service-url"]
          ? ["--im-service-url", values["im-service-url"]]
          : []),
      ];
      await import("./main.js");
    } else {
      applyGatewayEnvironment(config.value);
      const args = values["im-service-url"]
        ? ["--im-service-url", values["im-service-url"]]
        : [];
      const result = await manageGateway(
        configPath,
        config.value,
        action as "start" | "stop" | "restart" | "status",
        args,
      );
      process.stdout.write(result.text + "\n");
      if (!result.success) process.exitCode = 1;
    }
  } catch (error) {
    process.stderr.write(
      (error instanceof Error ? error.message : String(error)) + "\n",
    );
    process.exitCode = 1;
  }
