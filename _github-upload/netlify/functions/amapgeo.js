// Netlify Function (v2 / Web API)：代理高德 Web 服务 API（地理编码 / POI 搜索）
// 经 netlify.toml 重写，/api/amapgeo/* 会进入这里
// Key 从 Netlify 环境变量读取，浏览器永远接触不到

const PREFIXES = ["/api/amapgeo", "/.netlify/functions/amapgeo"];

function upstreamPath(u) {
  for (const prefix of PREFIXES) {
    if (u.pathname === prefix || u.pathname.startsWith(prefix + "/")) {
      return u.pathname.slice(prefix.length) || "/v3/geocode/geo";
    }
  }
  return "/v3/geocode/geo";
}

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export default async (req) => {
  const key = process.env.AMAP_WEB_KEY?.trim();

  if (!key) {
    return json(502, {
      error: "MISSING_KEY",
      message: "未配置 AMAP_WEB_KEY，请在 Netlify 站点设置的环境变量里填写高德 Web 服务 Key。",
    });
  }

  const url = new URL(req.url);
  const path = upstreamPath(url);

  const params = new URLSearchParams();
  for (const [k, v] of url.searchParams.entries()) {
    if (k === "key" || k === "p") continue;
    params.append(k, v);
  }
  params.set("key", key);

  const upstream = `https://restapi.amap.com${path}?${params.toString()}`;

  try {
    const upstreamRes = await fetch(upstream);
    // fetch 已自动解压，读 text 后直接返回，不转发 content-encoding
    const text = await upstreamRes.text();
    return new Response(text, {
      status: upstreamRes.status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } catch (err) {
    return json(500, { error: "PROXY_ERROR", message: String(err) });
  }
};
