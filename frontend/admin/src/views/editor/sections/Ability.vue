<template>
  <div class="space-y-4">
    <!-- Image and Name -->
    <div class="flex items-center gap-4" v-if="showImage">
      <img :src="imageUrl(ability.image)" class="w-16 h-16 rounded shadow" />
    </div>
    <div>
      <label class="block text-sm font-medium mb-1">Name</label>
      <input v-model="ability.name" class="w-full px-2 py-1 border rounded" />
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      <div>
        <label class="text-sm font-medium">Cost</label>
        <input v-model="ability.cost" class="w-full px-2 py-1 border rounded" />
      </div>
      <div>
        <label class="text-sm font-medium">Cooldown</label>
        <input v-model="ability.cooldown" class="w-full px-2 py-1 border rounded" />
      </div>
      <div>
        <label class="text-sm font-medium">Cast Time</label>
        <input v-model="ability.cast_time" class="w-full px-2 py-1 border rounded" />
      </div>
      <div>
        <label class="text-sm font-medium">Recharge</label>
        <input v-model="ability.recharge" class="w-full px-2 py-1 border rounded" />
      </div>
      <div v-if="showMaxrank">
        <label class="text-sm font-medium">Max Rank</label>
        <input type="number" v-model.number="ability.maxrank" class="w-full px-2 py-1 border rounded" />
      </div>
      <div v-if="showType">
        <label class="text-sm font-medium">Active Type</label>
        <select v-model="ability.type_" class="w-full px-2 py-1 border rounded">
          <option v-for="type in enums.activeTypes" :key="type.value" :value="type.value">
            {{ formatEnumLabel(type.name) }}
          </option>
        </select>
      </div>
      <div v-if="showUnique" class="flex items-center gap-2 mt-2">
        <input type="checkbox" v-model="ability.unique" />
        <label class="text-sm">Unique</label>
      </div>
    </div>

    <!-- Raw Stats -->
    <div>
      <h3 class="font-semibold text-sm mb-1">Raw Stats</h3>
      <div v-for="(value, key) in ability.raw_stats" :key="key" class="flex items-center gap-2 mb-2">
        <input :value="key" class="px-2 py-1 border rounded w-1/3 bg-gray-100 text-gray-700" disabled />
        <input :value="ability.raw_stats[key]" class="px-2 py-1 border rounded flex-1 bg-gray-100 text-gray-700" disabled />
        <button @click="removeRawStat(key)" class="text-red-600 font-semibold">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { toRefs, onMounted, ref } from 'vue'
import axios from 'axios'
import { formatEnumLabel } from '@/utils/formatters'

const props = defineProps({
  ability: Object,
  showImage: Boolean,
  showMaxrank: Boolean,
  showType: Boolean,
  showUnique: Boolean
})

const { ability } = toRefs(props)
const enums = ref({ activeTypes: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.activeTypes = data.ActiveType
})

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}

function removeRawStat(key) {
  delete ability.value.raw_stats[key]
}
</script>
