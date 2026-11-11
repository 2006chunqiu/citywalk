<script setup>
import { computed } from 'vue'

const props = defineProps({
  tags: { type: Array, required: true },
  modelValue: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue'])

const MAX = 4
const weights = [1.0, 0.7, 0.5, 0.4]

const chosen = computed(() => props.modelValue)
const chosenTags = computed(() =>
  chosen.value.map((id) => props.tags.find((t) => t.tagId === id)).filter(Boolean)
)

const isOn = (id) => chosen.value.includes(id)

function toggle(id) {
  if (isOn(id)) {
    emit('update:modelValue', chosen.value.filter((x) => x !== id))
    return
  }
  if (chosen.value.length >= MAX) {
    alert(`最多选择 ${MAX} 个标签，请先取消一个`)
    return
  }
  emit('update:modelValue', [...chosen.value, id])
}

function move(index, delta) {
  const next = [...chosen.value]
  const target = index + delta
  if (target < 0 || target >= next.length) return
  ;[next[index], next[target]] = [next[target], next[index]]
  emit('update:modelValue', next)
}
</script>

<template>
  <div>
    <div class="tags">
      <div
        v-for="t in tags"
        :key="t.tagId"
        class="tag"
        :class="{ on: isOn(t.tagId) }"
        @click="toggle(t.tagId)"
      >
        {{ t.name }}
      </div>
    </div>

    <div v-if="chosenTags.length" class="chosen">
      <div v-for="(t, i) in chosenTags" :key="t.tagId" class="chip">
        <b>{{ i + 1 }}</b>
        {{ t.name }}
        <span style="color: #8a919e">×{{ weights[i] }}</span>
        <a href="#" style="color: inherit" @click.prevent="move(i, -1)">↑</a>
        <a href="#" style="color: inherit" @click.prevent="move(i, 1)">↓</a>
      </div>
    </div>
    <div v-else class="gate">请至少选择一个兴趣标签</div>
  </div>
</template>
