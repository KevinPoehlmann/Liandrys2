<template>
  <div class="space-y-4">
    <!-- Image and Name -->
    <div class="flex items-center gap-4" v-if="showImage">
      <img :src="imageUrl(passive.image)" class="w-16 h-16 rounded shadow" />
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">Name</label>
      <input v-model="passive.name" class="w-full px-2 py-1 border rounded" />
    </div>

    <!-- Description -->
    <div>
      <label class="block text-sm font-medium mb-1">Description</label>
      <textarea v-model="passive.description" rows="3" class="w-full px-2 py-1 border rounded"></textarea>
    </div>

    <!-- Static Cooldown -->
    <div>
      <label class="block text-sm font-medium mb-1">Static Cooldown</label>
      <input v-model="passive.static_cooldown" class="w-full px-2 py-1 border rounded" />
    </div>

    <!-- Unique checkbox for items -->
    <div v-if="showUnique" class="flex items-center gap-2">
      <input type="checkbox" v-model="passive.unique" />
      <label class="text-sm">Unique</label>
    </div>

    <!-- Raw Stats -->
    <div>
      <h3 class="font-semibold mb-2">Raw Stats</h3>
      <div v-for="(value, key) in passive.raw_stats" :key="key" class="flex items-center gap-2 mb-2">
        <input :value="key" class="px-2 py-1 border rounded w-1/3 bg-gray-100 text-gray-700" disabled />
        <input :value="passive.raw_stats[key]" class="px-2 py-1 border rounded flex-1 bg-gray-100 text-gray-700" disabled />
        <button @click="removeRawStat(key)" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addRawStat" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Stat
      </button>
    </div>

    <PassiveEffect :effects="passive.effects" />

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
import { ref, toRefs } from 'vue'
import PassiveEffect from './PassiveEffect.vue'

const props = defineProps({
  passive: Object,
  showImage: Boolean,
  showUnique: Boolean
})

const { passive } = toRefs(props)

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}

function addRawStat() {
  const newKey = `stat_${Object.keys(passive.value.raw_stats).length + 1}`
  passive.value.raw_stats[newKey] = ''
}

function removeRawStat(key) {
  delete passive.value.raw_stats[key]
}
</script>
