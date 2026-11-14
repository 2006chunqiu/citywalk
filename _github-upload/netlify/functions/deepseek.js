// Netlify Function (v2 / Web API)：代理 DeepSeek API
// 经 netlify.toml 重写，/api/deepseek/* 会进入这里
// Key 从 Netlify 环境变量读取，浏览器永远接触不到

const PREFIXES = ["/api/deepseek", "/.netlify/functions/deepseek"];

function upstreamPath(url) {
  const u = new URL(url);
  for (const prefix of PREFIXES) {
    if (u.pathname === prefix || u.pathname.startsWith(prefix + "/")) {
      return u.pathname.slice(prefix.length) || "/v1/chat/completions";
    }
  }
  return "/v1/chat/completions";
}

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export default async (req) => {
  const key = process.env.DEEPSEEK_API_KEY?.trim();

  if (!key) {
    return json(502, {
      error: "MISSING_KEY",
      message: "未配置 DEEPSEEK_API_KEY，请在 Netlify 站点设置的环境变量里填写。",
    });
  }

  const path = upstreamPath(req.url);
  const hasBody = !["GET", "HEAD"].includes((req.method || "GET").toUpperCase());

  try {
    const upstreamRes = await fetch(`https://api.deepseek.com${path}`, {
      method: req.method || "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: hasBody ? await req.text() : undefined,
    });

    const text = await upstreamRes.text();
    return new Response(text, {
      status: upstreamRes.status,
      headers: {
        "Content-Type":
          upstreamRes.headers.get("content-type") || "application/json; charset=utf-8",
      },
    });
  } catch (err) {
    return json(500, { error: "PROXY_ERROR", message: String(err) });
  }
};
