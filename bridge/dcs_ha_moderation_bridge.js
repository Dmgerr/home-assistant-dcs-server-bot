"use strict";

const crypto = require("crypto");
const dgram = require("dgram");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const ROOT = process.env.DCSBOT_ROOT || "G:\\DCSServerBot";
const CONFIG_PATH = process.env.DCS_HA_BRIDGE_CONFIG || path.join(__dirname, "bridge.config.json");
const config = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
const nodesPath = path.join(ROOT, "config", "nodes.yaml");
const restApiPath = path.join(ROOT, "config", "plugins", "restapi.yaml");
const webservicePath = path.join(ROOT, "config", "services", "webservice.yaml");

function yamlScalar(text, key) {
  const match = text.match(new RegExp(`^\\s*${key}:\\s*['\"]?([^'\"#\\r\\n]+)`, "m"));
  if (!match) throw new Error(`Missing ${key} in configuration`);
  return match[1].trim();
}

function readRuntimeConfig() {
  const nodes = fs.readFileSync(nodesPath, "utf8");
  const restApi = fs.readFileSync(restApiPath, "utf8");
  const webservice = fs.readFileSync(webservicePath, "utf8");
  const instances = {};
  const lines = nodes.split(/\r?\n/);
  let inInstances = false;
  let current = null;
  for (const line of lines) {
    if (/^\s{2}instances:\s*$/.test(line)) {
      inInstances = true;
      continue;
    }
    if (!inInstances) continue;
    if (/^\S|^\s{0,1}\S/.test(line)) break;
    const instance = line.match(/^\s{4}([^:#]+):\s*$/);
    if (instance) {
      current = instance[1].trim();
      instances[current] = {};
      continue;
    }
    if (!current) continue;
    const value = line.match(/^\s{6}(bot_port|dcs_port):\s*(\d+)/);
    if (value) instances[current][value[1]] = Number(value[2]);
  }

  return {
    apiKey: yamlScalar(restApi, "api_key"),
    instances,
    restApiUrl: `http://${yamlScalar(webservice, "listen")}:${yamlScalar(webservice, "port")}`,
  };
}

function equalSecret(left, right) {
  const a = Buffer.from(String(left || ""));
  const b = Buffer.from(String(right || ""));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function remoteAllowed(address) {
  const normalized = String(address || "").replace(/^::ffff:/, "");
  return (config.allowed_ips || []).includes(normalized);
}

function audit(action, details) {
  const record = JSON.stringify({ time: new Date().toISOString(), action, ...details });
  fs.appendFileSync(config.audit_log || path.join(__dirname, "moderation-audit.log"), `${record}\n`, "utf8");
}

function sendJson(response, status, body) {
  const payload = Buffer.from(JSON.stringify(body));
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
  });
  response.end(payload);
}

async function readBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 32768) throw new Error("Request body too large");
    chunks.push(chunk);
  }
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
}

async function fetchServers(runtime) {
  const response = await fetch(`${runtime.restApiUrl}/servers`, {
    headers: { Accept: "application/json", "X-API-Key": runtime.apiKey },
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`DCSServerBot API returned HTTP ${response.status}`);
  return response.json();
}

async function serverBotPort(runtime, serverName) {
  const servers = await fetchServers(runtime);
  const server = servers.find((item) => item.name === serverName);
  if (!server) throw new Error("Unknown DCS server");
  const addressPort = Number(String(server.address || "").split(":").pop());
  const instance = Object.values(runtime.instances).find((item) => item.dcs_port === addressPort);
  if (!instance || !instance.bot_port) throw new Error("Cannot map DCS server to its bot UDP port");
  return instance.bot_port;
}

function sendUdp(port, command) {
  return new Promise((resolve, reject) => {
    const socket = dgram.createSocket("udp4");
    const payload = Buffer.from(JSON.stringify(command));
    socket.send(payload, port, "127.0.0.1", (error) => {
      socket.close();
      if (error) reject(error);
      else resolve();
    });
  });
}

function databaseCommand(action, payload = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(config.python_path, [path.join(__dirname, "moderation_db.py")], {
      windowsHide: true,
    });
    const stdout = [];
    const stderr = [];
    child.stdout.on("data", (chunk) => stdout.push(chunk));
    child.stderr.on("data", (chunk) => stderr.push(chunk));
    child.on("error", reject);
    child.on("close", (code) => {
      const raw = Buffer.concat(stdout).toString("utf8").trim();
      let result;
      try {
        result = JSON.parse(raw);
      } catch {
        return reject(new Error("Database helper returned invalid data"));
      }
      if (code === 0 && result.status === "ok") resolve(result);
      else reject(new Error(result.error || Buffer.concat(stderr).toString("utf8").trim() || "Database helper failed"));
    });
    child.stdin.end(JSON.stringify({ root: ROOT, action, ...payload }));
  });
}

async function handle(request, response) {
  const runtime = readRuntimeConfig();
  const remote = String(request.socket.remoteAddress || "").replace(/^::ffff:/, "");
  if (!remoteAllowed(remote)) return sendJson(response, 403, { error: "Remote address is not allowed" });
  if (!equalSecret(request.headers["x-api-key"], runtime.apiKey)) return sendJson(response, 401, { error: "Invalid API key" });

  if (request.method === "GET" && request.url === "/health") {
    return sendJson(response, 200, { status: "ok", service: "dcs-ha-moderation-bridge" });
  }
  if (request.method !== "POST") return sendJson(response, 404, { error: "Not found" });

  const body = await readBody(request);
  const playerName = String(body.player_name || "").trim();
  const reason = String(body.reason || "Moderation by Home Assistant").trim().slice(0, 240);
  if (!playerName || playerName.length > 128) return sendJson(response, 400, { error: "Invalid player_name" });

  if (request.url === "/kick") {
    const serverName = String(body.server_name || "").trim();
    const port = await serverBotPort(runtime, serverName);
    await sendUdp(port, { command: "kick", name: playerName, reason });
    audit("kick", { remote, server_name: serverName, player_name: playerName, reason, result: "sent" });
    return sendJson(response, 200, { status: "sent", action: "kick", player_name: playerName });
  }

  if (request.url === "/ban") {
    const requestedDays = Number(body.days || 0);
    if (!Number.isInteger(requestedDays) || requestedDays < 0 || requestedDays > 3650) {
      return sendJson(response, 400, { error: "days must be an integer from 0 to 3650" });
    }
    const days = requestedDays;
    const database = await databaseCommand("ban", { player_name: playerName, reason, days });
    const ucid = database.ucid;
    const until = days > 0 ? `${days} days` : "permanent";
    const bannedUntil = days > 0
      ? Math.floor(Date.now() / 1000) + Math.floor(days * 86400)
      : "never";
    await Promise.all(Object.values(runtime.instances)
      .filter((item) => item.bot_port)
      .map((item) => sendUdp(item.bot_port, { command: "ban", ucid, reason, banned_until: bannedUntil })));
    audit("ban", { remote, player_name: playerName, reason, days, result: "persisted_and_sent" });
    return sendJson(response, 200, { status: "ok", action: "ban", player_name: playerName, until });
  }

  if (request.url === "/unban") {
    const database = await databaseCommand("unban", { player_name: playerName });
    const ucid = database.ucid;
    await Promise.all(Object.values(runtime.instances)
      .filter((item) => item.bot_port)
      .map((item) => sendUdp(item.bot_port, { command: "unban", ucid })));
    audit("unban", { remote, player_name: playerName, result: "persisted_and_sent" });
    return sendJson(response, 200, { status: "ok", action: "unban", player_name: playerName });
  }

  return sendJson(response, 404, { error: "Not found" });
}

const server = http.createServer((request, response) => {
  handle(request, response).catch((error) => {
    audit("error", { remote: request.socket.remoteAddress, path: request.url, error: error.message });
    sendJson(response, 500, { error: error.message });
  });
});

server.listen(Number(config.port || 9877), config.bind, () => {
  audit("startup", { bind: config.bind, port: Number(config.port || 9877), result: "listening" });
});
