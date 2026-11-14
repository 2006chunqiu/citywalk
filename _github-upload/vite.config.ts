import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const deepseekKey = env.DEEPSEEK_API_KEY?.trim();
  const amapWebKey = env.AMAP_WEB_KEY?.trim();

  const proxyHeaders: Record<string, string> = {};
  if (deepseekKey) {
    proxyHeaders["Authorization"] = `Bearer ${deepseekKey}`;
  }
  proxyHeaders["Content-Type"] = "application/json";

  const deepseekProxyPlugin: Plugin = {
    name: "proxy-deepseek",
    configureServer(server) {
      server.middlewares.use("/api/deepseek", async (req, res, _next) => {
        if (!deepseekKey) {
          res.statusCode = 502;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(
            JSON.stringify({
              error: "MISSING_KEY",
              message:
                "未配置 DEEPSEEK_API_KEY，请在 .env 文件里填写。",
            })
          );
          return;
        }
        try {
          const path = req.url?.replace(/^\/api\/deepseek/, "") || "/v1/chat/completions";
          const upstream = `https://api.deepseek.com${path}`;
          const body = await readBody(req);
          const upstreamRes = await fetch(upstream, {
            method: req.method || "GET",
            headers: proxyHeaders,
            body: methodIsBody(req.method) ? body : undefined,
          });
          res.statusCode = upstreamRes.status;
          upstreamRes.headers.forEach((value, key) => {
            if (!hopByHop(key)) res.setHeader(key, value);
          });
          res.setHeader("Content-Type", upstreamRes.headers.get("content-type") || "application/json");
          const text = await upstreamRes.text();
          res.end(text);
        } catch (err) {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: "PROXY_ERROR", message: String(err) }));
        }
      });

      server.middlewares.use("/api/amapgeo", async (req, res) => {
        if (!amapWebKey) {
          res.statusCode = 502;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(
            JSON.stringify({
              error: "MISSING_KEY",
              message:
                "未配置 AMAP_WEB_KEY，请在 .env 文件里填写高德 Web 服务 Key。",
            })
          );
          return;
        }
        try {
          const url = new URL(req.url || "/", "https://restapi.amap.com/");
          url.searchParams.set("key", amapWebKey);
          const upstream = `https://restapi.amap.com${url.pathname}${url.search}`;
          const upstreamRes = await fetch(upstream);
          res.statusCode = upstreamRes.status;
          upstreamRes.headers.forEach((value, key) => {
            if (!hopByHop(key)) res.setHeader(key, value);
          });
          const text = await upstreamRes.text();
          res.end(text);
        } catch (err) {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: "PROXY_ERROR", message: String(err) }));
        }
      });
    },
  };

  return {
    plugins: [react(), tailwindcss(), deepseekProxyPlugin],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      host: true,
    },
  };
});

function hopByHop(header: string) {
  const list = new Set([
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "origin",
    "referer",
    // 我们用 upstreamRes.text() 已解压 body，不能再把压缩头转发
    "content-encoding",
    "content-length",
  ]);
  return list.has(header.toLowerCase());
}

function methodIsBody(method?: string) {
  const m = (method || "GET").toUpperCase();
  return m === "POST" || m === "PUT" || m === "PATCH" || m === "DELETE";
}

function readBody(req: unknown) {
  const chunks: Buffer[] = [];
  return new Promise<string>((resolve, reject) => {
    if (!req || typeof req !== "object") return resolve("");
    const r = req as {
      on?: (event: string, cb: (chunk: Buffer) => void) => void;
    };
    if (!r.on) return resolve("");
    r.on("data", (c: Buffer) => chunks.push(c));
    r.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    r.on("error", reject);
  });
}
