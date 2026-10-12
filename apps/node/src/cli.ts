#!/usr/bin/env node
import { parseArgs } from "node:util";
import { join, resolve } from "node:path";
import { homedir } from "node:os";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline/promises";
import { NodeConfiguration } from "./configuration.js";
import { manageGateway, applyGatewayEnvironment } from "./lifecycle.js";
import { bindDevice } from "./device-binding.js";
import { bootstrapNode } from "./bootstrap.js";
const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    config: { type: "string" },
    "source-root": {type: "string"},
    destination: {type: "string"},
    foreground: { type: "boolean" },
    "auto-bind": { type: "boolean" },
    "recover-device": { type: "boolean" },
    "im-service-url": { type: "string" },
    help: { type: "boolean", short: "h" },
  },
});
const command = positionals[0] ?? "start";
const action = command === "setup" ? "start" : command;
if (values.help) {
  process.stdout.write(
    "Usage: pnpm pa [setup|start|stop|restart|status|bind|migrate] [--config path] [--foreground] [--im-service-url URL] [--auto-bind] [--recover-device]\n",
  );
} else
  try {
    if (action === 'migrate') {
      if(!values['source-root']||!values.destination)throw new Error('Usage: pnpm pa migrate --source-root <old-owner-root> --destination <new-empty-directory>');
      const {migrateNode}=await import('./migration.js');
      const report=await migrateNode(values['source-root'],values.destination);
      process.stdout.write(JSON.stringify({nodeId:report.nodeId,counts:report.counts,blockers:report.blockers,readyForCutover:report.readyForCutover})+'\n');
      process.exit(report.blockers.length?2:0);
    }
    if (!["start", "stop", "restart", "status", "bind"].includes(action))
      throw new Error("Unknown personal-assistant command: " + action);
    if (command === "setup" && !values["im-service-url"])
      throw new Error("setup requires --im-service-url <your Nano IM address>");
    const config = command === "setup"
      ? await bootstrapNode(values["im-service-url"]!, values.config)
      : await NodeConfiguration.read(resolve(values.config ?? join(homedir(), ".nanoassistant/config.yaml")));
    const configPath = config.path;
    if (command === "setup") {
      process.stdout.write(`Nano connection: ${config.value.im_service.url}\nConfiguration: ${configPath}\n`);
      const current = await manageGateway(configPath, config.value, "status");
      if (current.state?.ready) {
        process.stdout.write("Your computer is already connected. Continue in the Nano webpage.\n");
        process.exit(0);
      }
    }
    if (["start", "restart"].includes(action))
      for (const agent of config.value.agents) config.runtime(agent);
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
