<template>
  <div class="min-h-screen flex flex-col bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
    <main class="flex flex-grow w-full px-4 py-6">
      <div class="flex flex-col w-full max-w-7xl mx-auto space-y-6">
        <!-- Patch Dropdown -->
        <div class="flex gap-4 items-center">
          <label class="text-sm font-semibold">Patch:</label>
          <select v-model="selectedPatchOption" class="p-1 rounded bg-white dark:bg-gray-700">
            <option
              v-for="entry in patchOptions"
              :key="entry.patch + '-' + (entry.hotfix || 'base')"
              :value="entry"
            >
              {{ entry.label }}
            </option>
          </select>
        </div>
        <div class="flex flex-col lg:flex-row gap-6">
          <!-- Blue Side -->
          <div class="flex-1 bg-blue-50 dark:bg-blue-900 p-4 rounded shadow">
            <h2 class="text-xl font-semibold mb-2">Blue Side</h2>
            <div class="flex items-center justify-center text-blue-800 dark:text-blue-100">
              <ChampionConfig
                team="blue"
                :config="blueConfig"
                @add="combo.push($event)"
              />
            </div>
          </div>

          <!-- Red Side -->
          <div class="flex-1 bg-red-50 dark:bg-red-900 p-4 rounded shadow">
            <h2 class="text-xl font-semibold mb-2 text-right">Red Side</h2>
            <div class="flex items-center justify-center text-red-800 dark:text-red-100">
              <ChampionConfig
                team="red"
                :config="redConfig"
                @add="combo.push($event)"
              />
            </div>
          </div>
        </div>

        <!-- Output / Timeline Area -->
        <div class="bg-gray-100 dark:bg-gray-800 p-6 rounded shadow">
          <h2 class="text-xl font-semibold mb-4">Simulation Output</h2>
          <div class="h-40 flex items-center justify-center text-gray-600 dark:text-gray-300">
            <SimulationOutput
              :blueConfig="blueConfig"
              :redConfig="redConfig"
              :combo="combo"
              :damage="damage"
              :time="time"
              @remove="combo.splice($event, 1)"
            />
          </div>
        </div>
        <div v-if="error" class="text-red-600 mt-2">{{ error }}</div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, provide, reactive, watch } from 'vue'
import ChampionConfig from './sections/ChampionConfig.vue'
import SimulationOutput from './sections/SimulationOutput.vue'


provide('patchContext', computed(() => (selectedPatchOption.value)))

const patchOptions = ref([])
const selectedPatchOption = ref(null)

const blueConfig = reactive({
  champion: null,
  level: 1,
  ability_points: {
    q: 0,
    w: 0,
    e: 0,
    r: 0
  },
  items: Array(6).fill(null),
  summonerspells: [null, null]
})
const redConfig = reactive({
  champion: null,
  level: 1,
  ability_points: {
    q: 0,
    w: 0,
    e: 0,
    r: 0
  },
  items: Array(6).fill(null),
  summonerspells: [null, null]
})

const combo = ref([])
const damage = ref(0)
const time = ref(0)

const error = ref(null)

const formatDateLabel = (timestamp) => {
  const date = new Date(timestamp)
  return `${date.getDate()} ${date.toLocaleString('en-US', { month: 'short' })}`
}

onMounted(async () => {
  const [latestRes, allRes] = await Promise.all([
    fetch('/patch/'),
    fetch('/patch/all')
  ])

  const latest = await latestRes.json()
  const all = await allRes.json()

  const options = []

  for (const patch of all) {
    if (patch.timestamp) {
      options.push({
        label: `${patch.patch} (${formatDateLabel(patch.timestamp)})`,
        patch: patch.patch,
        hotfix: patch.hotfix
      })
    }
    else {
      options.push({
        label: `${patch.patch}`,
        patch: patch.patch,
        hotfix: null
      })
    }
  }

  patchOptions.value = options

  // Select latest as default
  const latestMatch = options.find(p =>
    p.patch === latest.patch && (latest.hotfix ? p.hotfix === latest.hotfix : p.hotfix === null)
  )
  selectedPatchOption.value = latestMatch || options[0]
})


watch(
  () => [blueConfig.champion, redConfig.champion, combo.value],
  async () => {
    // Reset output
    damage.value = 0
    time.value = 0
    error.value = null

    // Require both champions and a non-empty combo
    if (!blueConfig.champion || !redConfig.champion || combo.value.length === 0) return

    try {
      const payload = {
        id_attacker: blueConfig.champion._id,
        id_defender: redConfig.champion._id,
        lvl_attacker: blueConfig.level,
        lvl_defender: redConfig.level,
        ability_points_attacker: blueConfig.ability_points,
        ability_points_defender: redConfig.ability_points,
        items_attacker: blueConfig.items.filter(Boolean).map(i => i.key),
        items_defender: redConfig.items.filter(Boolean).map(i => i.key),
        combo: combo.value
      }

      const res = await fetch('/simulation/v1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json()
        error.value = err.detail || 'Simulation failed.'
        return
      }

      const result = await res.json()
      damage.value = result.damage
      time.value = result.time

    } catch (e) {
      error.value = 'An unexpected error occurred.'
    }
  },
  { deep: true }
)


</script>

<style scoped>
/* Optional: Add animation or layout tuning here */
</style>
