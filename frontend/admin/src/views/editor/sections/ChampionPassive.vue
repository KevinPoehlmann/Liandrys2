<template>
  <div class="space-y-4">
    <!-- Image and Name -->
    <div class="flex items-center gap-4">
      <img :src="imageUrl(passive.image)" class="w-16 h-16 rounded shadow" />
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1">Name</label>
        <input v-model="local.name" class="w-full px-2 py-1 border rounded" />
      </div>
    </div>

    <!-- Description -->
    <div>
      <label class="block text-sm font-medium mb-1">Description</label>
      <textarea v-model="local.description" rows="3" class="w-full px-2 py-1 border rounded"></textarea>
    </div>

    <!-- Static Cooldown -->
    <div>
      <label class="block text-sm font-medium mb-1">Static Cooldown</label>
      <input v-model="local.static_cooldown" class="w-full px-2 py-1 border rounded" />
    </div>

    <!-- Raw Stats -->
    <div>
      <h3 class="font-semibold mb-2">Raw Stats</h3>
      <div v-for="(value, key) in local.raw_stats" :key="key" class="flex items-center gap-2 mb-2">
        <input v-model="keyEdit[key]" class="px-2 py-1 border rounded w-1/3" placeholder="Key" />
        <input v-model="local.raw_stats[key]" class="px-2 py-1 border rounded flex-1" placeholder="Value" />
        <button @click="removeRawStat(key)" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addRawStat" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Stat
      </button>
    </div>

    <PassiveEffect :effects="local.effects" @update="onEffectsUpdate" />

    <!-- Changes List -->
    <div v-if="passive.changes?.length" class="bg-yellow-100 border border-yellow-400 p-4 rounded">
      <h3 class="font-semibold mb-2">Manual Patch Changes to Review:</h3>
      <ul class="list-disc ml-5 text-sm">
        <li v-for="change in passive.changes" :key="change">{{ change }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, toRefs } from 'vue'
import PassiveEffect from './PassiveEffect.vue'

const props = defineProps({
  passive: Object,
})
const emit = defineEmits(['update'])

const { passive } = toRefs(props)
const local = ref({})
const keyEdit = ref({})

watch(passive, () => {
  local.value = {
    name: passive.value.name,
    description: passive.value.description,
    static_cooldown: passive.value.static_cooldown,
    raw_stats: { ...passive.value.raw_stats }
  }
  keyEdit.value = Object.fromEntries(Object.keys(local.value.raw_stats).map(k => [k, k]))
}, { immediate: true })

watch(local, () => {
  const diff = {}

  for (const key in local.value) {
    const original = passive.value[key]
    const current = local.value[key]

    // Deep comparison for raw_stats
    if (key === 'raw_stats') {
      if (JSON.stringify(original) !== JSON.stringify(current)) {
        diff[key] = current
      }
    } else if (original !== current) {
      diff[key] = current
    }
  }

  if (Object.keys(diff).length) {
    emit('update', diff)
  }
}, { deep: true })

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}

function addRawStat() {
  const newKey = `stat_${Object.keys(local.value.raw_stats).length + 1}`
  local.value.raw_stats[newKey] = ''
  keyEdit.value[newKey] = newKey
}

function removeRawStat(key) {
  delete local.value.raw_stats[key]
  delete keyEdit.value[key]
}

function onEffectsUpdate(newEffects) {
  local.value.effects = newEffects
}
</script>
