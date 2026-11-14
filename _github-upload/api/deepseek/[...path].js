// Vercel Serverless Function：代理 DeepSeek API
// 路由：/api/deepseek/*  ->  https://api.deepseek.com/*
// Key 从 Vercel 环境变量读取，浏览器永远接触不到
export default async function handler(req, res) {
  const key = process.env.DEEPSEEK_API_KEY?.trim();

  if (!key) {
    res.status(502).json({
      error: "MISSING_KEY",
      message: "未配置 DEEPSEEK_API_KEY，请在 Vercel 项目设置的环境变量里填写。",
    });
    return;
  }

  const segs = req.query.path;
  const path = Array.isArray(segs) ? "/" + segs.join("/") : "/v1/chat/completions";
  const upstream = `https://api.deepseek.com${path}`;

  try {
    const isBodyMethod = !["GET", "HEAD"].includes((req.method || "GET").toUpperCase());
    const body = isBodyMethod
      ? typeof req.body === "string"
        ? req.body
        : JSON.stringify(req.body ?? {})
      : undefined;

    const upstreamRes = await fetch(upstream, {
      method: req.method || "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body,
    });

    const text = await upstreamRes.text();
    res.status(upstreamRes.status);
    res.setHeader(
      "Content-Type",
      upstreamRes.headers.get("content-type") || "application/json; charset=utf-8"
    );
    res.send(text);
  } catch (err) {
    res.status(500).json({ error: "PROXY_ERROR", message: String(err) });
  }
}
