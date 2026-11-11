<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import TagPicker from '../components/TagPicker.vue'
import MapView from '../components/MapView.vue'
import { generate, tags as fetchTags, tips, isMock } from '../api/client'
import { fmtDistance, fmtDuration, haversineM } from '../utils/geo'

const STORAGE_KEY = 'citywalk.tags'

const allTags = ref([])
const selectedTags = ref([])
const effort = ref('normal')

const originQuery = ref('')
const destQuery = ref('')
const origin = ref(null)
const dest = ref(null)

const tipsFor = ref(null) // 'origin' | 'dest' | null
const tipList = ref([])

const loading = ref(false)
const error = ref('')
const result = ref(null)
const activeIndex = ref(0)

const activeScheme = computed(() => result.value?.schemes?.[activeIndex.value] || null)

const straight = computed(() => (origin.value && dest.value ? haversineM(origin.value, dest.value) : 0))
const tooClose = computed(() => straight.value > 0 && straight.value < 100)
const tooFar = computed(() => straight.value > 15000)
const canGenerate = computed(
  () => !!origin.value && !!dest.value && selectedTags.value.length > 0 && !tooClose.value && !tooFar.value && !loading.value
)

onMounted(async () => {
  allTags.value = await fetchTags()
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      const arr = JSON.parse(saved)
      selectedTags.value = arr.filter((id) => allTags.value.some((t) => t.tagId === id)).slice(0, 4)
    } catch { /* 忽略损坏的本地缓存 */ }
  }
})

watch(selectedTags, (v) => localStorage.setItem(STORAGE_KEY, JSON.stringify(v)), { deep: true })

let timer = null
function onInput(which, value) {
  clearTimeout(timer)
  tipsFor.value = which
  if (which === 'origin') origin.value = null
  else dest.value = null
  if (value.trim().length < 2) {
    tipList.value = []
    return
  }
  timer = setTimeout(async () => {
    try {
      tipList.value = await tips(value.trim())
    } catch {
      tipList.value = []
    }
  }, 300)
}

function pick(which, item) {
  if (which === 'origin') {
    origin.value = item
    originQuery.value = item.name
  } else {
    dest.value = item
    destQuery.value = item.name
  }
  tipList.value = []
  tipsFor.value = null
}

async function onGenerate() {
  if (!canGenerate.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const data = await generate({
      origin: { lng: origin.value.lng, lat: origin.value.lat },
      destination: { lng: dest.value.lng, lat: dest.value.lat },
      tagIds: selectedTags.value,
      tagOrder: selectedTags.value,
      effort: effort.value
    })
    if (data.status === 'fail') {
      error.value = '该区域暂无可推荐点位，请更换起终点或标签'
    } else {
      result.value = data
      activeIndex.value = 1 // 均衡版为默认
    }
  } catch (e) {
    error.value = e.message || '生成失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="wrap">
    <h1>漫步江城</h1>
    <div class="sub">
      输入起终点、选择兴趣标签，生成三条可走的步行路线。
      <span v-if="isMock" style="color: #c0392b">（当前为 mock 模式，数据是假的）</span>
    </div>

    <!-- 参数输入 -->
    <div class="card">
      <div class="row">
        <div class="tips">
          <div class="label">起点</div>
          <input
            v-model="originQuery"
            type="text"
            placeholder="输入地址，如 武汉大学"
            @input="onInput('origin', originQuery)"
          />
          <div v-if="tipsFor === 'origin' && tipList.length" class="tips-list">
            <div v-for="(t, i) in tipList" :key="i" class="tips-item" @click="pick('origin', t)">
              {{ t.name }}<span>{{ t.address }}</span>
            </div>
          </div>
        </div>
        <div class="tips">
          <div class="label">终点</div>
          <input
            v-model="destQuery"
            type="text"
            placeholder="输入地址，如 昙华林"
            @input="onInput('dest', destQuery)"
          />
          <div v-if="tipsFor === 'dest' && tipList.length" class="tips-list">
            <div v-for="(t, i) in tipList" :key="i" class="tips-item" @click="pick('dest', t)">
              {{ t.name }}<span>{{ t.address }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="straight > 0" class="gate">
        距终点约 {{ fmtDistance(straight) }}，步行约 {{ fmtDuration(straight / 1.25) }}
        <span v-if="tooClose" class="err">　起终点太近，请拉开距离</span>
        <span v-if="tooFar" class="err">　步行距离过长，建议改乘公共交通</span>
      </div>
    </div>

    <!-- 兴趣标签 -->
    <div class="card">
      <div class="label">兴趣标签（最多 4 个，顺序即优先级）</div>
      <TagPicker v-model="selectedTags" :tags="allTags" />
    </div>

    <!-- 体力等级与生成 -->
    <div class="card">
      <div class="row">
        <div>
          <div class="label">体力等级</div>
          <select v-model="effort">
            <option value="easy">轻松</option>
            <option value="normal">标准</option>
            <option value="deep">深度</option>
          </select>
        </div>
        <div style="flex: 0 0 auto">
          <button class="primary" :disabled="!canGenerate" @click="onGenerate">
            {{ loading ? '生成中…' : '生成路线' }}
          </button>
        </div>
      </div>
      <div v-if="error" class="err" style="margin-top: 10px">{{ error }}</div>
    </div>

    <!-- 结果 -->
    <template v-if="result && activeScheme">
      <div class="card">
        <div class="label">方案对比（点击切换）</div>
        <div class="plans">
          <div
            v-for="(s, i) in result.schemes"
            :key="s.schemeId"
            class="plan"
            :class="{ on: i === activeIndex }"
            @click="activeIndex = i"
          >
            <h4>{{ { shortest: '最短路线', max: '兴趣最大化', balanced: '均衡' }[s.mode] }}</h4>
            <dl>
              <dt>距离</dt><dd>{{ fmtDistance(s.distanceM) }}</dd>
              <dt>耗时</dt><dd>{{ fmtDuration(s.durationS) }}</dd>
              <dt>途经点</dt><dd>{{ s.waypointCount }} 个</dd>
              <dt>绕行</dt><dd>×{{ s.detourRatio }}</dd>
            </dl>
          </div>
        </div>
        <div class="reason">{{ activeScheme.reason }}</div>
      </div>

      <div class="card">
        <div class="label">路线</div>
        <MapView
          :polyline="activeScheme.polyline"
          :waypoints="activeScheme.waypoints"
          :origin="origin"
          :destination="dest"
        />
        <div style="margin-top: 12px">
          <div v-for="wp in activeScheme.waypoints" :key="wp.poiId" class="wp">
            <b>{{ wp.seq }}</b>　{{ wp.name }}
            <i>{{ wp.typeName }} · 建议停留 {{ wp.stayMinutes }} 分钟 ·
              {{ wp.rating ?? '—' }} · 距上一点 {{ fmtDistance(wp.distanceFromPrevM) }}</i>
            <span class="src">{{ { amap: '高德接口', seed: '种子库', keyword: '关键词补充', hot: '热门推荐' }[wp.source] || wp.source }}</span>
          </div>
        </div>
      </div>
    </template>

    <div class="sub" style="margin-top: 24px">
      接口与字段定义见 <code>docs/api.md</code>；本地假数据在 <code>src/mock/</code>。
    </div>
  </div>
</template>
