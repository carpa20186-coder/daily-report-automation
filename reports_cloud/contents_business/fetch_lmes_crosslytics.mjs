#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const ENDPOINT = process.env.LMES_MCP_ENDPOINT || "https://mcp.lmes.jp/mcp";
const DEFAULT_BOT = process.env.LMES_BOT || "長倉顕太【コンテンツビジネスの始め方】";
const DEFAULT_CROSS_ID = Number(process.env.LMES_CROSS_ID || 14869);

function parseArgs(argv) {
  const args = {
    bot: DEFAULT_BOT,
    crossId: DEFAULT_CROSS_ID,
    out: "reports_cloud/contents_business/data/contents_crosslytics_14869.json",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === "--bot") {
      args.bot = value;
      i += 1;
    } else if (key === "--cross-id") {
      args.crossId = Number(value);
      i += 1;
    } else if (key === "--out") {
      args.out = value;
      i += 1;
    } else {
      throw new Error(`Unknown argument: ${key}`);
    }
  }

  if (!Number.isFinite(args.crossId)) {
    throw new Error("--cross-id must be a number");
  }
  return args;
}

function findLocalTokenFile() {
  const root = path.join(os.homedir(), ".mcp-auth");
  if (!fs.existsSync(root)) return null;

  const files = [];
  for (const dir of fs.readdirSync(root)) {
    const fullDir = path.join(root, dir);
    if (!fs.statSync(fullDir).isDirectory()) continue;
    for (const file of fs.readdirSync(fullDir)) {
      if (!file.endsWith("_tokens.json")) continue;
      const fullPath = path.join(fullDir, file);
      files.push({ path: fullPath, mtimeMs: fs.statSync(fullPath).mtimeMs });
    }
  }
  files.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return files[0]?.path || null;
}

function readAccessToken() {
  if (process.env.LMES_ACCESS_TOKEN) {
    return process.env.LMES_ACCESS_TOKEN;
  }

  const tokenFile = process.env.LMES_TOKEN_FILE || findLocalTokenFile();
  if (!tokenFile) {
    throw new Error("Set LMES_ACCESS_TOKEN or LMES_TOKEN_FILE.");
  }

  const token = JSON.parse(fs.readFileSync(tokenFile, "utf8"));
  if (!token.access_token) {
    throw new Error("LMES token file does not contain access_token.");
  }
  return token.access_token;
}

let requestId = 1;

async function requestMcp(message) {
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${readAccessToken()}`,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    },
    body: JSON.stringify(message),
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`LMES MCP HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  return text.trim() ? JSON.parse(text) : null;
}

async function initMcp() {
  await requestMcp({
    jsonrpc: "2.0",
    id: requestId++,
    method: "initialize",
    params: {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: { name: "contents-business-cloud-report", version: "0.1.0" },
    },
  });
  await requestMcp({
    jsonrpc: "2.0",
    method: "notifications/initialized",
    params: {},
  });
}

async function callTool(name, args) {
  const response = await requestMcp({
    jsonrpc: "2.0",
    id: requestId++,
    method: "tools/call",
    params: { name, arguments: args },
  });

  if (response?.error) {
    throw new Error(`${name}: ${response.error.message}`);
  }

  const text = response?.result?.content?.[0]?.text ?? "";
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function listAll(toolName, args, key) {
  const first = await callTool(toolName, { ...args, page: 1, limit: 100 });
  const items = [...(first[key] ?? [])];
  const total = first.pagination?.total ?? items.length;
  const pages = Math.ceil(total / 100);

  for (let page = 2; page <= pages; page += 1) {
    const result = await callTool(toolName, { ...args, page, limit: 100 });
    items.push(...(result[key] ?? []));
  }
  return items;
}

async function resolveBot(botQuery) {
  const bots = await listAll("list_bots", {}, "bots");
  return (
    bots.find((bot) => bot.id === botQuery) ||
    bots.find((bot) => bot.view_name === botQuery) ||
    bots.find((bot) => bot.view_name?.includes(botQuery))
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  await initMcp();

  const bot = await resolveBot(args.bot);
  if (!bot) {
    throw new Error(`Bot not found: ${args.bot}`);
  }

  const result = await callTool("get_crosslytics_result", {
    bot_id: bot.id,
    cross_id: args.crossId,
  });

  fs.mkdirSync(path.dirname(args.out), { recursive: true });
  fs.writeFileSync(args.out, JSON.stringify(result, null, 2), "utf8");
  console.log(`Wrote LMES crosslytics: ${args.out}`);
  console.log(`bot=${bot.view_name} (${bot.id}), cross_id=${args.crossId}, date=${result.date ?? "-"}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
