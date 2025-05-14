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
              <ChampionConfig team="blue" :config="blueConfig"/>
            </div>
          </div>

          <!-- Red Side -->
          <div class="flex-1 bg-red-50 dark:bg-red-900 p-4 rounded shadow">
            <h2 class="text-xl font-semibold mb-2 text-right">Red Side</h2>
            <div class="flex items-center justify-center text-red-800 dark:text-red-100">
              <ChampionConfig team="red" :config="redConfig"/>
            </div>
          </div>
        </div>

        <!-- Output / Timeline Area -->
        <div class="bg-gray-100 dark:bg-gray-800 p-6 rounded shadow">
          <h2 class="text-xl font-semibold mb-4">Simulation Output</h2>
          <div class="h-40 flex items-center justify-center text-gray-600 dark:text-gray-300">
            Output Placeholder (damage, time, timeline...)
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import ChampionConfig from './sections/ChampionConfig.vue'

const blueConfig = ref({ champion: null, level: 1 })
const redConfig = ref({ champion: null, level: 1 })

const patchOptions = ref([])
const selectedPatchOption = ref(null)

onMounted(async () => {
  const [latestRes, allRes] = await Promise.all([
    fetch('/patch/'),
    fetch('/patch/all')
  ])

  const latest = await latestRes.json()
  const all = await allRes.json()

  const options = []

  for (const patch of all) {
    options.push({
      label: patch.patch,
      patch: patch.patch,
      hotfix: null
    })

    if (patch.hotfix) {
      options.push({
        label: patch.patch + ' (Hotfix)', // TODO: refine label logic
        patch: patch.patch,
        hotfix: patch.hotfix
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
</script>

<style scoped>
/* Optional: Add animation or layout tuning here */
</style>
