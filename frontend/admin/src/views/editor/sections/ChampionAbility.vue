<template>
  <div class="space-y-4">
    <!-- Image and Name -->
    <div class="flex items-center gap-4">
      <img :src="imageUrl(ability.image)" class="w-16 h-16 rounded shadow" />
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1">Name</label>
        <input v-model="local.name" class="w-full px-2 py-1 border rounded" />
      </div>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      <div>
        <label class="text-sm font-medium">Cost</label>
        <input v-model="local.cost" class="w-full px-2 py-1 border rounded" />
      </div>
      <div>
        <label class="text-sm font-medium">Cooldown</label>
        <input v-model="local.cooldown" class="w-full px-2 py-1 border rounded" />
      </div>
      <div>
        <label class="text-sm font-medium">Cast Time</label>
        <input v-model="local.cast_time" class="w-full px-2 py-1 border rounded" />
      </div>
      <div>
        <label class="text-sm font-medium">Recharge</label>
        <input v-model="local.recharge" class="w-full px-2 py-1 border rounded" />
      </div>
    </div>

    <!-- Description -->
    <div>
      <label class="block text-sm font-medium">Description</label>
      <textarea v-model="local.description" rows="3" class="w-full px-2 py-1 border rounded"></textarea>
    </div>

    <h3 class="font-semibold text-sm mt-6">Effects</h3>
    <div class="space-y-4">
      <Effect
        v-for="(effect, i) in local.effects"
        :key="i"
        v-model="local.effects[i]"
      />
      <button @click="addEffect" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Effect
      </button>
    </div>

    <!-- Raw Stats (reused logic like in passive) -->
    <div>
      <h3 class="font-semibold text-sm mb-1">Raw Stats</h3>
      <div v-for="(value, key) in local.raw_stats" :key="key" class="flex items-center gap-2 mb-2">
        <input v-model="keyEdit[key]" class="px-2 py-1 border rounded w-1/3" placeholder="Key" />
        <input v-model="local.raw_stats[key]" class="px-2 py-1 border rounded flex-1" placeholder="Value" />
        <button @click="removeRawStat(key)" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addRawStat" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Stat
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, toRefs } from 'vue'
import Effect from './Effect.vue'

const props = defineProps({ ability: Object })
const emit = defineEmits(['update'])

const { ability } = toRefs(props)
const local = ref({})
const keyEdit = ref({})

watch(ability, () => {
  local.value = {
    name: ability.value.name,
    description: ability.value.description,
    cost: ability.value.cost,
    cooldown: ability.value.cooldown,
    cast_time: ability.value.cast_time,
    recharge: ability.value.recharge,
    effects: ability.value.effects,
    raw_stats: { ...ability.value.raw_stats }
  }
  keyEdit.value = Object.fromEntries(Object.keys(local.value.raw_stats).map(k => [k, k]))
}, { immediate: true })

watch(local, () => {
  const diff = {}
  for (const key in local.value) {
    const original = ability.value[key]
    const current = local.value[key]

    if (key === 'raw_stats') {
      if (JSON.stringify(original) !== JSON.stringify(current)) {
        diff[key] = current
      }
    } else if (original !== current) {
      diff[key] = current
    }
  }
  if (Object.keys(diff).length) emit('update', diff)
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

function addEffect() {
  local.value.effects = [...(local.value.effects || []), { text: '', effect_components: [], conditions: [] }]
}
</script>
