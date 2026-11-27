#!/usr/bin/env node
import { randomUUID } from "node:crypto";
import { windowsHost } from "./windows-platform.js";
import { loadNodeRelease } from "./release.js";
import { nodeUpdateTerminal, type NodeUpdateReport } from "@nano/product-contracts";
import { parseArgs } from "node:util";
import { join, resolve } from "node:path";
import { homedir } from "node:os";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline/promises";
import { NodeConfiguration } from "./configuration.js";
import { manageGateway, applyGatewayEnvironment, browserPairingFile } from "./lifecycle.js";
import { bindDevice } from "./device-binding.js";
import { bootstrapNode } from "./bootstrap.js";
const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    config: { type: "string" },
    origin: { type: "string" },
    "owner-id": { type: "string" },
    "log-query": { type: "string" },
    "source-root": {type: "string"},
    destination: {type: "string"},
    foreground: { type: "boolean" },
    profile: { type: "string" },
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
    "Usage: pnpm pa [setup|start|stop|restart|status|bind|migrate|local-admin|browser pair|browser status|browser disconnect] [--config path] [--foreground] [--im-service-url URL] [--auto-bind] [--recover-device]\n",
  );
} else
  try {
    if (action === "browser") {
      const config = await NodeConfiguration.read(resolve(values.config ?? join(homedir(), ".nanoassistant/config.yaml")));
      if (!config.value.node.user_id) throw new Error("Bind this node before pairing a browser.");
      const {browserCommand} = await import("./browser-pairing.js");
      const result = await browserCommand(positionals[1] ?? "status", browserPairingFile(config.path, config.value.node), values.profile ?? "Default");
      process.stdout.write(JSON.stringify(result) + "\n");
      process.exit(0);
    }
    if (action === "local-admin") {
      const subcommand = positionals[1] ?? "inspect";
      const origin = values.origin ?? values["im-service-url"];
      if (!origin) throw new Error("local-admin requires --origin <IM URL>");
      const {
        LocalAdminHttpError,
        connectLocalNode,
        controlLocalNodeLifecycle,
        inspectLocalNode,
        manageLocalNodeBrowser,
        probeDesktopWorkers,
        resolveLocalWorkspaceTarget,
        updateLocalNodeConfig,
      } = await import("./local-admin.js");
      const readStdinJson = async (): Promise<Record<string, unknown>> => {
        if (process.stdin.isTTY) return {};
        const chunks: Buffer[] = [];
        for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
        const text = Buffer.concat(chunks).toString("utf8").trim();
        return text ? (JSON.parse(text) as Record<string, unknown>) : {};
      };
      try {
        let payload: unknown;
        if (subcommand === "inspect") {
          payload = await inspectLocalNode({
            supervisionOnly: positionals[2] === "supervision",
            origin,
            ownerId: values["owner-id"],
            configPath: values.config,
            logQuery: values["log-query"],
          });
        } else if (subcommand === "probe-workers") {
          const input = await readStdinJson();
          const current = await inspectLocalNode({ origin, ownerId: values["owner-id"], configPath: values.config });
          if (current.ownership === "foreign_owner") {
            throw new LocalAdminHttpError(403, "foreign_owner", "This computer belongs to another account");
          }
          payload = { workers: await probeDesktopWorkers(typeof input.path === "string" ? input.path : undefined) };
        } else if (subcommand === "browser") {
          const input = await readStdinJson();
          payload = await manageLocalNodeBrowser({
            origin,
            ownerId: values["owner-id"] ?? "",
            actionInput: input as unknown as import("@nano/product-contracts").DesktopBrowserActionInput,
            configPath: values.config,
          });
        } else if (subcommand === "connect") {
          const input = await readStdinJson();
          payload = await connectLocalNode({
            origin,
            ownerId: values["owner-id"] ?? "",
            accessToken: String(input.access_token ?? ""),
            confirmTransfer: Boolean(input.confirm_transfer),
            configPath: values.config,
            activeMetadata: input.active_metadata as Record<string, string> | undefined,
          });
        } else if (subcommand === "lifecycle") {
          const input = await readStdinJson();
          const lifeAction = String(input.action ?? "");
          if (!["start", "stop", "restart", "autostart-on", "autostart-off"].includes(lifeAction)) {
            throw new LocalAdminHttpError(400, "invalid_action", "Unsupported lifecycle action");
          }
          payload = await controlLocalNodeLifecycle({
            origin,
            ownerId: values["owner-id"] ?? "",
            action: lifeAction as "start" | "stop" | "restart" | "autostart-on" | "autostart-off",
            preserveUserStopped: Boolean(input.preserve_user_stopped),
            configPath: values.config,
          });
        } else if (subcommand === "config") {
          const input = await readStdinJson();
          payload = await updateLocalNodeConfig({
            origin,
            ownerId: values["owner-id"] ?? "",
            update: input as unknown as import("@nano/product-contracts").DesktopLocalConfigInput,
            configPath: values.config,
          });
        } else if (subcommand === "resolve-workspace") {
          const input = await readStdinJson();
          const mode = input.mode === "open" ? "open" : "reveal";
          payload = await resolveLocalWorkspaceTarget({
            origin,
            ownerId: values["owner-id"] ?? "",
            agentId: String(input.agent_id ?? ""),
            targetPath: String(input.target_path ?? ""),
            mode,
            configPath: values.config,
          });
        } else {
          throw new LocalAdminHttpError(400, "unknown_subcommand", `Unknown local-admin subcommand: ${subcommand}`);
        }
        process.stdout.write(JSON.stringify({ ok: true, status: 200, data: payload }) + "\n");
        process.exit(0);
      } catch (adminError) {
        if (adminError instanceof LocalAdminHttpError) {
          process.stdout.write(
            JSON.stringify({
              ok: false,
              status: adminError.status,
              error_code: adminError.errorCode,
              message: adminError.message,
              ...(adminError.details ?? {}),
            }) + "\n",
          );
          process.exit(2);
        }
        throw adminError;
      }
    }
    if (action === 'migrate') {
      if(!values['source-root']||!values.destination)throw new Error('Usage: pnpm pa migrate --source-root <old-owner-root> --destination <new-empty-directory>');
      const {migrateNode}=await import('./migration.js');
      const report=await migrateNode(values['source-root'],values.destination);
      process.stdout.write(JSON.stringify({nodeId:report.nodeId,counts:report.counts,blockers:report.blockers,readyForCutover:report.readyForCutover})+'\n');
      process.exit(report.blockers.length?2:0);
    }
    if (!["start", "stop", "restart", "status", "bind", "autostart-on", "autostart-off", "autostart-status"].includes(action))
      throw new Error("Unknown personal-assistant command: " + action);
    if (command === "setup" && !values["im-service-url"])
      throw new Error("setup requires --im-service-url <your Nano IM address>");
    const config = command === "setup"
      ? await bootstrapNode(values["im-service-url"]!, values.config)
      : await NodeConfiguration.read(resolve(values.config ?? join(homedir(), ".nanoassistant/config.yaml")));
    const configPath = config.path;
    const reconnect = process.platform === "win32" && command === "setup" && !!config.value.node.user_id && !!config.value.im_service.token;
    const returnToSetup = async () => {
      if (!reconnect) return;
      const url = new URL("/onboarding", config.value.im_service.url);
      url.searchParams.set("node", config.value.node.node_id);
      await windowsHost("open-browser", url.href);
    };
    if (command === "setup") {
      process.stdout.write(`Nano connection: ${config.value.im_service.url}\nConfiguration: ${configPath}\n`);
      let current = await manageGateway(configPath, config.value, "status");
      if (reconnect && !current.state) current = await manageGateway(configPath, config.value, "start");
      if (current.state?.ready) {
        const target = await loadNodeRelease();
        if (target.kind === 'source' || current.state.release?.sha256 === target.sha256) {
          await returnToSetup();
          process.stdout.write("Your computer is already connected. Continue in the Nano webpage.\n");
          process.exit(0);
        }
        if (current.state.release?.kind === 'source') throw new Error('This computer runs a source checkout. Update it using its original deployment method.');
        if (current.state.release?.updater_protocol === 1) {
          const response = await fetch(new URL('/im/v1/node-update/report', config.value.im_service.url), {
            method: 'POST', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${config.value.im_service.token}`},
            body: JSON.stringify({node_id: config.value.node.node_id, action: 'request_install', request_id: randomUUID(), version: target.version, sha256: target.sha256}),
            signal: AbortSignal.timeout(10000),
          });
          if (!response.ok) throw new Error('The selected installation version is no longer available. Run the installation command again.');
          const report = await response.json() as NodeUpdateReport;
          process.stdout.write('Update requested. Existing work will finish before the computer switches. You can follow or cancel it in Nano.\n');
          // The detached worker owns liveness; this CLI must not keep a crashed worker alive in IM.
          if (nodeUpdateTerminal(report.operation.state) && report.operation.state !== 'succeeded')
            throw new Error(`Update finished: ${report.operation.state}. Open Nano for recovery instructions.`);
          await returnToSetup();
          process.exit(0);
        }
        process.stdout.write('Enabling safe updates for this older installation. Existing tasks must be finished before running this command. Preserving your configuration and workspace.\n');
        await manageGateway(configPath, config.value, 'stop');
      }
    }
    if (["start", "restart"].includes(action)) {
      config.validateNodeSettings();
      for (const agent of config.value.agents) config.runtime(agent);
    }
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
        open: async (url) => {
          if (process.platform === "win32") {
            await windowsHost("open-browser", url);
            return;
          }
          const child = spawn(
            process.platform === "darwin" ? "open" : "xdg-open",
            [url],
            { stdio: "ignore" },
          );
          child.on("error", () => {});
          child.unref();
        },
        confirm: async (text) => {
          if (process.platform === "win32") return await windowsHost("confirm-transfer", text) === "yes";
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
