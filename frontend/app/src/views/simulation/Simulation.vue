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
          <!-- <label class="text-sm font-semibold">Map:</label>
          <select v-model="selectedMapOption" class="p-1 rounded bg-white dark:bg-gray-700">
            <option
              v-for="entry in mapOptions"
              :key="entry"
              :value="entry"
            >
              {{ entry }}
            </option>
          </select> -->
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
          <div class=" flex items-center justify-center text-gray-600 dark:text-gray-300">
            <SimulationOutput
              :blueConfig="blueConfig"
              :redConfig="redConfig"
              :combo="combo"
              :damage="damage"
              :ticks="ticks"
              :tickRate="tickRate"
              :lastActionTick="lastActionTick"
              :deaths="deaths"
              :effectList="effectList"
              :error="error"
              @remove="combo.splice($event, 1)"
            />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, provide, reactive, watch } from 'vue'
import ChampionConfig from './sections/ChampionConfig.vue'
import SimulationOutput from './sections/SimulationOutput.vue'
import { buildUrl } from '@/utils/fetch'


provide('patchContext', computed(() => (selectedPatchOption.value)))
provide('mapContext', computed(() => (selectedMapOption.value)))
provide("champions", computed(() => (champions.value)))
provide("items", computed(() => (items.value)))
provide("runes", computed(() => (runes.value)))
provide("summonerspells", computed(() => (summonerspells.value)))

const patchOptions = ref([])
const selectedPatchOption = ref(null)
const mapOptions = ref([])
const selectedMapOption = ref(null)

const champions = ref([])
const items = ref([])
const runes = ref([])
const summonerspells = ref([])

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
  runes: {
    primary: {
      treeId: null,
      runes: Array(4).fill(null)
    },
    secondary: {
      treeId: null,
      runes: Array(4).fill(null)
    },
    shards: Array(3).fill(null)
  },
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
  runes: {
    primary: {
      treeId: null,
      runes: Array(4).fill(null)
    },
    secondary: {
      treeId: null,
      runes: Array(4).fill(null)
    },
    shards: Array(3).fill(null)
  },
  summonerspells: [null, null]
})

const combo = ref([])
const damage = ref(0)
const ticks = ref(0)
const tickRate = ref(0)
const lastActionTick = ref(0)
const deaths = ref({})
const effectList = ref([])

const error = ref(null)

const formatDateLabel = (timestamp) => {
  const date = new Date(timestamp)
  return `${date.getDate()} ${date.toLocaleString('en-US', { month: 'short' })}`
}


onMounted(async () => {
  const [latestRes, allRes, enumRes] = await Promise.all([
    fetch('/patch/'),
    fetch('/patch/all'),
    fetch('/item/map/')
  ])

  const latest = await latestRes.json()
  const all = await allRes.json()
  const mapEnums = await enumRes.json()
  const options = []

  for (const patch of all) {
    if (patch.hotfix) {
      options.push({
        label: `${patch.patch} (${formatDateLabel(patch.hotfix)})`,
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
  mapOptions.value = mapEnums.map(m => m.value)
  //selectedMapOption.value = mapOptions.value[0]
  selectedMapOption.value = "SR"

  // Select latest as default
  const latestMatch = options.find(p =>
    p.patch === latest.patch && (latest.hotfix ? p.hotfix === latest.hotfix : p.hotfix === null)
  )
  selectedPatchOption.value = latestMatch || options[0]
  await loadPatchData()
  for (const config of [blueConfig, redConfig]) {
    config.summonerspells[0] = summonerspells.value.find(s => s.key === 'SummonerFlash')
    config.summonerspells[1] = summonerspells.value.find(s => s.key === 'SummonerDot')
  }
})


async function loadPatchData() {
  const { patch, hotfix } = selectedPatchOption.value
  const map = selectedMapOption.value

  const [championList, itemList, runeList, summonerspellList] = await Promise.all([
    fetch(buildUrl('/champion/all', patch, { hotfix })).then(res => res.json()),
    fetch(buildUrl('/item/all', patch, { hotfix, map })).then(res => res.json()),
    fetch(buildUrl('/rune/all', patch, { hotfix })).then(res => res.json()),
    fetch(buildUrl('/summonerspell/all', patch, { hotfix, map })).then(res => res.json())
  ])
  champions.value = championList
  items.value = itemList
  runes.value = runeList
  summonerspells.value = summonerspellList
}


// Every patch has its own documents (and _ids), so selections are matched to the new patch by their stable keys.
function findInPatch(list, old, isSame) {
  if (!old) return null
  return list.find(entry => isSame(entry, old)) ?? null
}

function remapConfig(config) {
  const sameRune = (a, b) => a.rune_id === b.rune_id && a.row === b.row
  config.champion = findInPatch(champions.value, config.champion, (a, b) => a.champion_id === b.champion_id)
  config.items = config.items.map(item => findInPatch(items.value, item, (a, b) => a.item_id === b.item_id))
  config.summonerspells = config.summonerspells.map(spell => findInPatch(summonerspells.value, spell, (a, b) => a.key === b.key))
  config.runes.primary.runes = config.runes.primary.runes.map(rune => findInPatch(runes.value, rune, sameRune))
  config.runes.secondary.runes = config.runes.secondary.runes.map(rune => findInPatch(runes.value, rune, sameRune))
  config.runes.shards = config.runes.shards.map(rune => findInPatch(runes.value, rune, sameRune))
}


watch([selectedPatchOption, selectedMapOption], async (_, [oldPatch]) => {
  if (!oldPatch) return  // initial load happens in onMounted
  await loadPatchData()
  remapConfig(blueConfig)
  remapConfig(redConfig)
})


watch(
  () => [blueConfig.champion, redConfig.champion, blueConfig.level, redConfig.level, blueConfig.ability_points, redConfig.ability_points, combo.value, blueConfig.items, redConfig.items],
  async () => {
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
        items_attacker: blueConfig.items.filter(Boolean).map(i => i._id),
        items_defender: redConfig.items.filter(Boolean).map(i => i._id),
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
      else {
        error.value = null
      }

      const result = await res.json()
      damage.value = result.damage
      ticks.value = result.ticks
      tickRate.value = result.tick_rate
      lastActionTick.value = result.last_action_tick
      deaths.value = result.deaths ?? {}
      effectList.value = result.effect_list

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
