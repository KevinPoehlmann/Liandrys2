<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <!-- Base Stats -->
    <div>
      <h3 class="font-semibold mb-2">Stats</h3>
      <div v-for="(value, key) in stats" :key="key" class="flex items-center gap-2 mb-2">
        <select v-model="statKeys[key]" @change="renameStatKey(key, statKeys[key], 'stats')" class="px-2 py-1 border rounded w-1/3">
          <option v-for="stat in enums.stats" :key="stat.value" :value="stat.value">
            {{ formatEnumLabel(stat.name) }}
          </option>
        </select>
        <input type="number" v-model.number="stats[statKeys[key]]" class="px-2 py-1 border rounded flex-1" />
        <button @click="removeStat(statKeys[key])" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addStat(stats)" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Stat
      </button>
    </div>

    <!-- Masterwork Stats -->
    <div>
      <h3 class="font-semibold mb-2">Masterwork Stats</h3>
      <div v-for="(value, key) in masterwork" :key="key" class="flex items-center gap-2 mb-2">
        <select v-model="statKeysMasterwork[key]" @change="renameStatKey(key, statKeysMasterwork[key], 'masterwork')" class="px-2 py-1 border rounded w-1/3">
          <option v-for="stat in enums.stats" :key="stat.value" :value="stat.value">
            {{ formatEnumLabel(stat.name) }}
          </option>
        </select>
        <input type="number" v-model.number="masterwork[statKeysMasterwork[key]]" class="px-2 py-1 border rounded flex-1" />
        <button @click="removeMasterwork(statKeysMasterwork[key])" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addStat(masterwork, true)" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Masterwork
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { formatEnumLabel } from '@/utils/formatters'

const props = defineProps({
  stats: Object,
  masterwork: Object
})

const enums = ref({ stats: [] })
const statKeys = ref({})
const statKeysMasterwork = ref({})

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.stats = data.Stat

  // Initialize key maps
  for (const key in props.stats) statKeys.value[key] = key
  for (const key in props.masterwork) statKeysMasterwork.value[key] = key
})

function addStat(target, isMasterwork = false) {
  const availableStats = enums.value.stats.map(s => s.value)
  const used = new Set(Object.keys(isMasterwork ? props.masterwork : props.stats))
  const unused = availableStats.find(s => !used.has(s)) || `stat_${used.size + 1}`

  if (isMasterwork) {
    props.masterwork[unused] = 0
    statKeysMasterwork.value[unused] = unused
  } else {
    props.stats[unused] = 0
    statKeys.value[unused] = unused
  }
}

function renameStatKey(oldKey, newKey, type) {
  if (oldKey === newKey) return
  const target = type === 'stats' ? props.stats : props.masterwork
  const keysMap = type === 'stats' ? statKeys.value : statKeysMasterwork.value

  target[newKey] = target[oldKey]
  delete target[oldKey]

  keysMap[newKey] = newKey
  delete keysMap[oldKey]
}

function removeStat(key) {
  delete props.stats[key]
  delete statKeys.value[key]
}

function removeMasterwork(key) {
  delete props.masterwork[key]
  delete statKeysMasterwork.value[key]
}
</script>
