const USE_MOCK = String(import.meta.env.VITE_MOCK ?? 'true') === 'true'

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = new Error(data?.error?.message || `请求失败 (${res.status})`)
    err.code = data?.error?.code || 'HTTP_' + res.status
    throw err
  }
  return data
}

/** 地址输入提示；mock 模式下返回固定候选 */
export async function tips(keywords) {
  if (USE_MOCK) {
    const { tips: list } = await import('../mock/tips.json')
    return list.filter((t) => t.name.includes(keywords) || keywords.length <= 2).slice(0, 8)
  }
  const data = await request(`/api/tips?keywords=${encodeURIComponent(keywords)}&city=武汉`)
  return data.tips
}

/** 生成三条方案 */
export async function generate(payload) {
  if (USE_MOCK) {
    const { generate: data } = await import('../mock/route.json')
    await new Promise((r) => setTimeout(r, 600)) // 模拟 600ms 网络
    return JSON.parse(JSON.stringify(data))
  }
  return request('/api/route/generate', { method: 'POST', body: JSON.stringify(payload) })
}

export async function tags() {
  if (USE_MOCK) {
    const { tags: list } = await import('../mock/tags.json')
    return list
  }
  const data = await request('/api/tags')
  return data.tags
}

export async function health() {
  if (USE_MOCK) return { ok: true, llm: 'mock', amap: 'mock', keyPool: { total: 0, alive: 0 } }
  return request('/api/health')
}

export const isMock = USE_MOCK
