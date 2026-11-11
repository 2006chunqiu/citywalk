<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  polyline: { type: Array, default: () => [] }, // [[lng, lat], ...]
  waypoints: { type: Array, default: () => [] },
  origin: { type: Object, default: null },
  destination: { type: Object, default: null }
})

const el = ref(null)
const state = ref('loading') // loading | ready | nokey | error
const msg = ref('')

let map = null
let overlays = []
let AMapRef = null

const KEY = import.meta.env.VITE_AMAP_JS_KEY
const SECRET = import.meta.env.VITE_AMAP_JS_SECRET

function loadScript() {
  return new Promise((resolve, reject) => {
    if (window.AMap) return resolve(window.AMap)
    if (!KEY) return reject(new Error('NOKEY'))
    if (SECRET) window._AMapSecurityConfig = { securityJsCode: SECRET }
    const s = document.createElement('script')
    s.src = `https://webapi.amap.com/maps?v=2.0&key=${KEY}`
    s.onload = () => resolve(window.AMap)
    s.onerror = () => reject(new Error('加载高德 JS API 失败'))
    document.head.appendChild(s)
  })
}

function clearOverlays() {
  overlays.forEach((o) => map && map.remove(o))
  overlays = []
}

function draw() {
  if (!map || !AMapRef) return
  clearOverlays()

  if (props.polyline.length > 1) {
    const line = new AMapRef.Polyline({
      path: props.polyline,
      strokeColor: '#2b6cb0',
      strokeWeight: 6,
      strokeOpacity: 0.9,
      lineJoin: 'round',
      showDir: true
    })
    map.add(line)
    overlays.push(line)
  }

  props.waypoints.forEach((wp, i) => {
    const marker = new AMapRef.Marker({
      position: [wp.lng, wp.lat],
      content: `<div style="width:22px;height:22px;border-radius:50%;background:#2b6cb0;color:#fff;
        font-size:12px;line-height:22px;text-align:center;border:2px solid #fff;
        box-shadow:0 1px 4px rgba(0,0,0,.3)">${i + 1}</div>`,
      offset: new AMapRef.Pixel(-11, -11),
      title: wp.name
    })
    map.add(marker)
    overlays.push(marker)
  })

  const pins = [
    { p: props.origin, color: '#27ae60', label: '起' },
    { p: props.destination, color: '#c0392b', label: '终' }
  ]
  pins.forEach(({ p, color, label }) => {
    if (!p || !p.lng) return
    const marker = new AMapRef.Marker({
      position: [p.lng, p.lat],
      content: `<div style="width:24px;height:24px;border-radius:6px;background:${color};color:#fff;
        font-size:12px;line-height:24px;text-align:center;border:2px solid #fff;
        box-shadow:0 1px 4px rgba(0,0,0,.3)">${label}</div>`,
      offset: new AMapRef.Pixel(-12, -12),
      title: p.name || label
    })
    map.add(marker)
    overlays.push(marker)
  })

  if (overlays.length) map.setFitView(overlays, false, [40, 40, 40, 40])
}

onMounted(async () => {
  try {
    AMapRef = await loadScript()
    map = new AMapRef.Map(el.value, {
      zoom: 14,
      center: [114.3300, 30.5450],
      viewMode: '2D'
    })
    state.value = 'ready'
    draw()
  } catch (e) {
    if (e.message === 'NOKEY') {
      state.value = 'nokey'
      msg.value = '未配置 VITE_AMAP_JS_KEY，地图不显示。在 .env 里填上高德 JS API Key 与安全密钥后重启 dev。'
    } else {
      state.value = 'error'
      msg.value = e.message
    }
  }
})

onBeforeUnmount(() => {
  if (map) map.destroy()
  map = null
})

watch(() => [props.polyline, props.waypoints], draw, { deep: true })
</script>

<template>
  <div class="map" ref="el">
    <div v-if="state !== 'ready'" class="map-hint">
      {{ state === 'loading' ? '地图加载中…' : msg }}
    </div>
  </div>
</template>
