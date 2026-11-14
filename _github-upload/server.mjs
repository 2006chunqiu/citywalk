// 生产环境服务器：托管 dist 静态文件 + 代理 DeepSeek / 高德 Web 服务
// 零外部依赖，Node 20+ 直接运行
import { createServer } from "node:http";
import { createReadStream, existsSync } from "node:fs";
import { stat } from "node:fs/promises";
import { join, extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
// 部署时 server.mjs 与 index.html 同在 dist/；本地从项目根运行时回落到 ./dist
const STATIC_DIR = existsSync(join(HERE, "index.html")) ? HERE : join(HERE, "dist");
const PORT = Number(process.env.PORT || 8000);
const MAX_BODY = 2 * 1024 * 1024;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".map": "application/json; charset=utf-8",
};

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolvePromise, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY) {
        reject(new Error("请求体过大"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolvePromise(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

async function proxyDeepSeek(req, res, url) {
  const key = (process.env.DEEPSEEK_API_KEY || "").trim();
  if (!key) {
    return sendJson(res, 502, {
      error: "MISSING_KEY",
      message: "未配置 DEEPSEEK_API_KEY 环境变量。",
    });
  }

  const path = url.pathname.replace(/^\/api\/deepseek/, "") || "/v1/chat/completions";
  const hasBody = !["GET", "HEAD"].includes((req.method || "GET").toUpperCase());

  const upstream = await fetch(`https://api.deepseek.com${path}`, {
    method: req.method || "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: hasBody ? await readBody(req) : undefined,
  });

  const text = await upstream.text();
  res.writeHead(upstream.status, {
    "Content-Type": upstream.headers.get("content-type") || "application/json; charset=utf-8",
  });
  res.end(text);
}

async function proxyAmap(req, res, url) {
  const key = (process.env.AMAP_WEB_KEY || "").trim();
  if (!key) {
    return sendJson(res, 502, {
      error: "MISSING_KEY",
      message: "未配置 AMAP_WEB_KEY 环境变量。",
    });
  }

  const path = url.pathname.replace(/^\/api\/amapgeo/, "") || "/v3/geocode/geo";
  const params = new URLSearchParams(url.searchParams);
  params.delete("key");
  params.set("key", key);

  const upstream = await fetch(`https://restapi.amap.com${path}?${params.toString()}`);
  const text = await upstream.text();
  res.writeHead(upstream.status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(text);
}

async function serveStatic(req, res, url) {
  if (!["GET", "HEAD"].includes((req.method || "GET").toUpperCase())) {
    res.writeHead(405, { Allow: "GET, HEAD" });
    return res.end();
  }

  let pathname;
  try {
    pathname = decodeURIComponent(url.pathname);
  } catch {
    return sendJson(res, 400, { error: "BAD_REQUEST" });
  }
  if (pathname === "/") pathname = "/index.html";

  let filePath = resolve(STATIC_DIR, "." + pathname);
  if (filePath !== STATIC_DIR && !filePath.startsWith(STATIC_DIR + sep)) {
    return sendJson(res, 403, { error: "FORBIDDEN" });
  }

  let info = await stat(filePath).catch(() => null);
  if (!info || !info.isFile()) {
    // 单页应用兜底
    filePath = join(STATIC_DIR, "index.html");
    info = await stat(filePath).catch(() => null);
    if (!info) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      return res.end("Not Found");
    }
  }

  const type = MIME[extname(filePath).toLowerCase()] || "application/octet-stream";
  const headers = { "Content-Type": type, "Content-Length": info.size };
  if (filePath.includes(`${sep}assets${sep}`)) {
    headers["Cache-Control"] = "public, max-age=31536000, immutable";
  }
  res.writeHead(200, headers);
  if (req.method === "HEAD") return res.end();
  createReadStream(filePath).pipe(res);
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
    if (url.pathname.startsWith("/api/deepseek")) return await proxyDeepSeek(req, res, url);
    if (url.pathname.startsWith("/api/amapgeo")) return await proxyAmap(req, res, url);
    return await serveStatic(req, res, url);
  } catch (err) {
    console.error("[server]", err);
    if (!res.headersSent) sendJson(res, 500, { error: "INTERNAL", message: String(err) });
    else res.end();
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`citywalk server listening on 0.0.0.0:${PORT}, static=${STATIC_DIR}`);
});
