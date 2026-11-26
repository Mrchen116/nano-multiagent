#!/usr/bin/env node
/**
 * Controllable local WeChat iLink + CDN twin for isolated worktree E2E verification.
 *
 * Exposes standard iLink Bot CGI endpoints (`/ilink/bot/*`), AES-128-ECB CDN
 * endpoints (`/c2c/download`, `/c2c/upload`), and local test control endpoints
 * (`/__admin/*`). Never contacts real Tencent servers.
 */
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { EventEmitter } from "node:events";
import { writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, resolve } from "node:path";

function parseArgs(argv) {
  let port = 0;
  let stateFile = "";
  let pidFile = "";
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--port") port = Number(argv[++i] ?? 0);
    else if (argv[i] === "--state") stateFile = resolve(argv[++i] ?? "");
    else if (argv[i] === "--pid-file") pidFile = resolve(argv[++i] ?? "");
  }
  if (!pidFile && stateFile) {
    pidFile = resolve(dirname(stateFile), ".wechat-twin.pid");
  }
  return { port, stateFile, pidFile };
}

const { port: requestedPort, stateFile, pidFile } = parseArgs(process.argv.slice(2));
const bus = new EventEmitter();
bus.setMaxListeners(100);

let seqCounter = 0;
let qrCounter = 0;
let msgCounter = 0;
const qrSessions = new Map();
const inboundQueue = [];
const sentMessages = [];
const typingEvents = [];
const configCalls = [];
const mediaBlobs = new Map();
const uploadedMedia = new Map();
const revokedTokens = new Set();
const activePollersByToken = new Map();
const maxConcurrentPollersByToken = new Map();

function persistSnapshot(boundPort) {
  if (!stateFile) return;
  const snapshot = {
    port: boundPort,
    base_url: `http://127.0.0.1:${boundPort}`,
    qr_sessions: Array.from(qrSessions.values()),
    sent_messages: sentMessages,
    typing_events: typingEvents,
    active_pollers: Object.fromEntries(activePollersByToken),
    max_concurrent_pollers: Object.fromEntries(maxConcurrentPollersByToken),
    revoked_tokens: Array.from(revokedTokens),
  };
  writeFileSync(stateFile, JSON.stringify(snapshot, null, 2));
}

function readRawBody(req) {
  return new Promise((resolveBody, rejectBody) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolveBody(Buffer.concat(chunks)));
    req.on("error", rejectBody);
  });
}

async function readJsonBody(req) {
  const raw = await readRawBody(req);
  if (raw.length === 0) return {};
  return JSON.parse(raw.toString("utf8"));
}

function sendJson(res, status, payload, extraHeaders = {}) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    ...extraHeaders,
  });
  res.end(body);
}

function extractBearerToken(req) {
  const header = String(req.headers.authorization ?? "");
  return header.startsWith("Bearer ") ? header.slice(7).trim() : "";
}

function encryptAes128Ecb(plaintext, keyBuf) {
  const cipher = createCipheriv("aes-128-ecb", keyBuf, null);
  return Buffer.concat([cipher.update(plaintext), cipher.final()]);
}

function decryptAes128Ecb(ciphertext, keyBuf) {
  const decipher = createDecipheriv("aes-128-ecb", keyBuf, null);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

const server = createServer(async (req, res) => {
  try {
    const boundPort = server.address()?.port ?? requestedPort;
    const baseUrl = `http://127.0.0.1:${boundPort}`;
    const url = new URL(req.url ?? "/", baseUrl);
    const { pathname, searchParams } = url;

    // ─── Admin Control Plane ───────────────────────────────────────────────────
    if (pathname === "/__admin/health" && req.method === "GET") {
      return sendJson(res, 200, { ok: true, port: boundPort, base_url: baseUrl });
    }

    if (pathname === "/__admin/state" && req.method === "GET") {
      return sendJson(res, 200, {
        port: boundPort,
        base_url: baseUrl,
        qr_sessions: Array.from(qrSessions.values()),
        sent_messages: sentMessages,
        typing_events: typingEvents,
        config_calls: configCalls,
        active_pollers: Object.fromEntries(activePollersByToken),
        max_concurrent_pollers: Object.fromEntries(maxConcurrentPollersByToken),
        uploaded_media: Array.from(uploadedMedia.entries()).map(([key, item]) => ({
          key,
          cipher_size: item.ciphertext.length,
          plaintext_size: item.plaintext ? item.plaintext.length : null,
          plaintext_base64: item.plaintext ? item.plaintext.toString("base64") : null,
        })),
        revoked_tokens: Array.from(revokedTokens),
      });
    }

    if (pathname === "/__admin/reset" && req.method === "POST") {
      sentMessages.length = 0;
      typingEvents.length = 0;
      configCalls.length = 0;
      inboundQueue.length = 0;
      revokedTokens.clear();
      persistSnapshot(boundPort);
      return sendJson(res, 200, { ok: true });
    }

    if (pathname === "/__admin/qr" && req.method === "POST") {
      const body = await readJsonBody(req);
      const targetCode = body.qrcode || Array.from(qrSessions.keys()).at(-1);
      if (!targetCode || !qrSessions.has(targetCode)) {
        return sendJson(res, 404, { error: "no_active_qr_session" });
      }
      const session = qrSessions.get(targetCode);
      session.status = body.status ?? session.status;
      if (body.expected_pin !== undefined) session.expected_pin = String(body.expected_pin);
      if (body.redirect_host !== undefined) session.redirect_host = String(body.redirect_host);
      if (body.bot_token !== undefined) session.bot_token = String(body.bot_token);
      if (body.bot_id !== undefined) session.bot_id = String(body.bot_id);
      if (body.owner_user_id !== undefined) session.owner_user_id = String(body.owner_user_id);
      if (body.baseurl !== undefined) session.baseurl = String(body.baseurl);
      persistSnapshot(boundPort);
      return sendJson(res, 200, { ok: true, session });
    }

    if (pathname === "/__admin/media" && req.method === "POST") {
      const body = await readJsonBody(req);
      const rawBuf = body.plaintext_base64
        ? Buffer.from(body.plaintext_base64, "base64")
        : Buffer.from(String(body.plaintext_utf8 ?? ""), "utf8");
      const keyBuf = body.aes_key_hex
        ? Buffer.from(body.aes_key_hex, "hex")
        : randomBytes(16);
      const aesKeyHex = keyBuf.toString("hex");
      const cipherBuf = encryptAes128Ecb(rawBuf, keyBuf);
      const queryParam = body.encrypt_query_param || `dl_${randomBytes(8).toString("hex")}`;
      const aesKeyEncoding = body.key_encoding || "raw_base64";
      const aesKeyBase64 = aesKeyEncoding === "hex_ascii_base64"
        ? Buffer.from(aesKeyHex, "utf8").toString("base64")
        : keyBuf.toString("base64");
      mediaBlobs.set(queryParam, cipherBuf);
      return sendJson(res, 200, {
        encrypt_query_param: queryParam,
        aes_key_hex: aesKeyHex,
        aes_key_base64: aesKeyBase64,
        raw_size: rawBuf.length,
        cipher_size: cipherBuf.length,
        raw_md5: createHash("md5").update(rawBuf).digest("hex"),
      });
    }

    if (pathname === "/__admin/inbound" && req.method === "POST") {
      const body = await readJsonBody(req);
      seqCounter += 1;
      msgCounter += 1;
      const message = {
        seq: seqCounter,
        message_id: body.message_id ?? 900_000 + msgCounter,
        ...(body.svr_id !== undefined ? { svr_id: body.svr_id } : {}),
        from_user_id: body.from_user_id ?? "wxid_owner_3k92",
        to_user_id: body.to_user_id ?? "bot_wx_twin",
        create_time_ms: body.create_time_ms ?? Date.now(),
        message_type: body.message_type ?? 1,
        message_state: body.message_state ?? 2,
        context_token: body.context_token ?? `ctx_${seqCounter}`,
        item_list: body.item_list ?? [{ type: 1, text_item: { text: String(body.text ?? "") } }],
      };
      inboundQueue.push({
        cursor: seqCounter,
        bot_token: body.bot_token ?? null,
        message,
      });
      persistSnapshot(boundPort);
      bus.emit("wake");
      return sendJson(res, 200, { ok: true, seq: seqCounter, message });
    }

    if (pathname === "/__admin/revoke" && req.method === "POST") {
      const body = await readJsonBody(req);
      if (body.bot_token) {
        revokedTokens.add(String(body.bot_token));
      } else {
        for (const s of qrSessions.values()) {
          if (s.bot_token) revokedTokens.add(s.bot_token);
        }
      }
      persistSnapshot(boundPort);
      bus.emit("wake");
      return sendJson(res, 200, { ok: true, revoked_tokens: Array.from(revokedTokens) });
    }

    // ─── iLink Bot CGI Endpoints ───────────────────────────────────────────────
    if (pathname === "/ilink/bot/get_bot_qrcode" && (req.method === "GET" || req.method === "POST")) {
      if (req.method === "POST") await readRawBody(req);
      qrCounter += 1;
      const qrcode = `qr_twin_${qrCounter}_${Date.now()}`;
      const session = {
        qrcode,
        qrcode_img_content: `https://ilinkai.weixin.qq.com/qr/${qrcode}`,
        status: "wait",
        expected_pin: "482916",
        bot_token: `tok_twin_${qrCounter}`,
        bot_id: `bot_twin_${qrCounter}`,
        owner_user_id: "wxid_owner_3k92",
        baseurl: baseUrl,
      };
      qrSessions.set(qrcode, session);
      persistSnapshot(boundPort);
      return sendJson(res, 200, {
        ret: 0,
        qrcode,
        qrcode_img_content: session.qrcode_img_content,
      });
    }

    if (
      (pathname === "/ilink/bot/get_qrcode_status" && req.method === "GET") ||
      (pathname === "/ilink/bot/verify_qrcode_code" && req.method === "POST")
    ) {
      let qrcode = searchParams.get("qrcode") ?? "";
      let verifyCode = searchParams.get("verify_code") ?? "";
      if (req.method === "POST") {
        const body = await readJsonBody(req);
        qrcode = qrcode || String(body.qrcode ?? "");
        verifyCode = verifyCode || String(body.verify_code ?? body.code ?? "");
      }
      const session = qrSessions.get(qrcode);
      if (!session) {
        return sendJson(res, 200, { ret: 0, status: "expired" });
      }
      if (verifyCode) {
        if (session.status === "verify_code_blocked") {
          return sendJson(res, 200, {
            ret: 0,
            status: "verify_code_blocked",
            errmsg: "验证码尝试次数过多，请重新扫码",
          });
        }
        if (verifyCode !== session.expected_pin) {
          return sendJson(res, 200, {
            ret: 0,
            status: "need_verifycode",
            errmsg: "验证码不正确，请核对手机微信界面显示的数字后重试",
          });
        }
        session.status = "confirmed";
      }
      if (session.status === "confirmed") {
        persistSnapshot(boundPort);
        return sendJson(res, 200, {
          ret: 0,
          status: "confirmed",
          bot_token: session.bot_token,
          ilink_bot_id: session.bot_id,
          ilink_user_id: session.owner_user_id,
          baseurl: session.baseurl,
        });
      }
      return sendJson(res, 200, {
        ret: 0,
        status: session.status,
        ...(session.redirect_host ? { redirect_host: session.redirect_host } : {}),
      });
    }

    if (pathname === "/ilink/bot/getupdates" && req.method === "POST") {
      const token = extractBearerToken(req);
      const body = await readJsonBody(req);
      const activeNow = (activePollersByToken.get(token) ?? 0) + 1;
      activePollersByToken.set(token, activeNow);
      maxConcurrentPollersByToken.set(
        token,
        Math.max(maxConcurrentPollersByToken.get(token) ?? 0, activeNow),
      );
      let cleaned = false;
      const release = () => {
        if (cleaned) return;
        cleaned = true;
        activePollersByToken.set(token, Math.max(0, (activePollersByToken.get(token) ?? 1) - 1));
      };
      res.on("close", release);

      try {
        if (revokedTokens.has(token)) {
          return sendJson(res, 200, { ret: 0, errcode: -14, errmsg: "session expired" });
        }
        const prevCursor = Number(body.get_updates_buf || "0") || 0;
        const collectReady = () => inboundQueue.filter(
          (item) => item.cursor > prevCursor && (!item.bot_token || item.bot_token === token),
        );
        let ready = collectReady();
        if (ready.length === 0) {
          await new Promise((resolveWait) => {
            const onWake = () => {
              clearTimeout(timer);
              bus.off("wake", onWake);
              resolveWait();
            };
            const timer = setTimeout(() => {
              bus.off("wake", onWake);
              resolveWait();
            }, 900);
            res.once("close", onWake);
            bus.on("wake", onWake);
          });
          if (res.writableEnded || res.destroyed) return;
          if (revokedTokens.has(token)) {
            return sendJson(res, 200, { ret: 0, errcode: -14, errmsg: "session expired" });
          }
          ready = collectReady();
        }
        const nextCursor = ready.length > 0 ? String(ready.at(-1).cursor) : String(prevCursor);
        return sendJson(res, 200, {
          ret: 0,
          errcode: 0,
          msgs: ready.map((item) => item.message),
          get_updates_buf: nextCursor,
          longpolling_timeout_ms: 1000,
        });
      } finally {
        release();
      }
    }

    if (pathname === "/ilink/bot/sendmessage" && req.method === "POST") {
      const token = extractBearerToken(req);
      if (revokedTokens.has(token)) {
        return sendJson(res, 200, { ret: 0, errcode: -14, errmsg: "session expired" });
      }
      const body = await readJsonBody(req);
      const outMsgId = String(950_000 + sentMessages.length + 1);
      sentMessages.push({
        received_at: new Date().toISOString(),
        bot_token: token,
        message_id: outMsgId,
        msg: body.msg,
      });
      persistSnapshot(boundPort);
      return sendJson(res, 200, { ret: 0, errcode: 0, message_id: outMsgId });
    }

    if (pathname === "/ilink/bot/getconfig" && req.method === "POST") {
      const body = await readJsonBody(req);
      configCalls.push({ received_at: new Date().toISOString(), ...body });
      return sendJson(res, 200, { ret: 0, errcode: 0, typing_ticket: "twin_typing_ticket" });
    }

    if (pathname === "/ilink/bot/sendtyping" && req.method === "POST") {
      const body = await readJsonBody(req);
      typingEvents.push({ received_at: new Date().toISOString(), ...body });
      persistSnapshot(boundPort);
      return sendJson(res, 200, { ret: 0, errcode: 0 });
    }

    if (pathname === "/ilink/bot/getuploadurl" && req.method === "POST") {
      const body = await readJsonBody(req);
      const filekey = String(body.filekey ?? randomBytes(8).toString("hex"));
      uploadedMedia.set(filekey, {
        aeskey_hex: String(body.aeskey ?? ""),
        rawsize: Number(body.rawsize ?? 0),
        filesize: Number(body.filesize ?? 0),
        ciphertext: Buffer.alloc(0),
        plaintext: null,
      });
      return sendJson(res, 200, {
        ret: 0,
        errcode: 0,
        upload_param: `upload_${filekey}`,
        upload_full_url: `${baseUrl}/c2c/upload?upload_param=upload_${encodeURIComponent(filekey)}&filekey=${encodeURIComponent(filekey)}`,
      });
    }

    // ─── CDN Endpoints ─────────────────────────────────────────────────────────
    if (pathname === "/c2c/upload" && req.method === "POST") {
      const filekey = searchParams.get("filekey") ?? "";
      const ciphertext = await readRawBody(req);
      const existing = uploadedMedia.get(filekey) ?? { aeskey_hex: "", ciphertext: Buffer.alloc(0), plaintext: null };
      let plaintext = null;
      if (existing.aeskey_hex && existing.aeskey_hex.length === 32) {
        try {
          plaintext = decryptAes128Ecb(ciphertext, Buffer.from(existing.aeskey_hex, "hex"));
        } catch {
          plaintext = null;
        }
      }
      const encParam = `enc_${filekey}`;
      uploadedMedia.set(filekey, { ...existing, ciphertext, plaintext });
      mediaBlobs.set(encParam, ciphertext);
      persistSnapshot(boundPort);
      res.writeHead(200, {
        "x-encrypted-param": encParam,
        "content-length": "0",
      });
      res.end();
      return;
    }

    if (pathname === "/c2c/download" && req.method === "GET") {
      const param = searchParams.get("encrypted_query_param") ?? "";
      const blob = mediaBlobs.get(param);
      if (!blob) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      res.writeHead(200, {
        "content-type": "application/octet-stream",
        "content-length": blob.length,
      });
      res.end(blob);
      return;
    }

    sendJson(res, 404, { error: "not_found", path: pathname });
  } catch (error) {
    sendJson(res, 500, {
      error: "twin_internal_error",
      detail: error instanceof Error ? error.message : String(error),
    });
  }
});

server.listen(requestedPort, "127.0.0.1", () => {
  const boundPort = server.address()?.port ?? requestedPort;
  if (pidFile) {
    writeFileSync(pidFile, String(process.pid));
  }
  persistSnapshot(boundPort);
  process.stdout.write(`e2e-wechat-twin listening on http://127.0.0.1:${boundPort}\n`);
});
