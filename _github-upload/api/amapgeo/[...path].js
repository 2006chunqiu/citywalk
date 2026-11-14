// Vercel Serverless Function：代理高德 Web 服务 API（地理编码 / POI 搜索）
// 路由：/api/amapgeo/*  ->  https://restapi.amap.com/*
// Key 从 Vercel 环境变量读取，浏览器永远接触不到
export default async function handler(req, res) {
  const key = process.env.AMAP_WEB_KEY?.trim();

  if (!key) {
    res.status(502).json({
      error: "MISSING_KEY",
      message: "未配置 AMAP_WEB_KEY，请在 Vercel 项目设置的环境变量里填写高德 Web 服务 Key。",
    });
    return;
  }

  const segs = req.query.path;
  const path = Array.isArray(segs) ? "/" + segs.join("/") : "/v3/geocode/geo";

  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(req.query)) {
    if (k === "path" || k === "key") continue;
    if (Array.isArray(v)) v.forEach((item) => params.append(k, String(item)));
    else if (v !== undefined) params.append(k, String(v));
  }
  params.set("key", key);

  const upstream = `https://restapi.amap.com${path}?${params.toString()}`;

  try {
    const upstreamRes = await fetch(upstream);
    // fetch 已自动解压，这里读 text 后直接返回，不转发 content-encoding
    const text = await upstreamRes.text();
    res.status(upstreamRes.status);
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.send(text);
  } catch (err) {
    res.status(500).json({ error: "PROXY_ERROR", message: String(err) });
  }
}
