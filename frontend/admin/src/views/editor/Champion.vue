<template>
  <div v-if="champion" class="p-6 space-y-6">
    <h1 class="text-2xl font-bold">Champion Editor</h1>

    <!-- Top Info Block -->
    <div class="flex items-center gap-4">
      <img :src="imageUrl(champion?.image)" class="w-20 h-20 rounded shadow" />
      <div>
        <p><strong>Name:</strong> {{ champion?.name }}</p>
        <p><strong>Key:</strong> {{ champion?.key }}</p>
        <p><strong>ID:</strong> {{ champion?.id }}</p>
        <p><strong>Champion ID:</strong> {{ champion?.champion_id }}</p>
        <p><strong>Patch:</strong> {{ champion?.patch }}</p>
        <p><strong>Hotfix:</strong> {{ champion?.hotfix || '—' }}</p>
        <p><strong>Last Changed:</strong> {{ champion?.last_changed }}</p>
      </div>
    </div>

    <!-- Collapsible Sections -->
    <details open>
      <summary class="text-lg font-semibold cursor-pointer">Base Stats</summary>
      <ChampionStats :champion="champion" @update="onSectionUpdate('stats', $event)" />
    </details>

    <details>
      <summary class="text-lg font-semibold cursor-pointer">Passive</summary>
      <ChampionPassive :passive="champion?.passive" @update="onSectionUpdate('passive', $event)" />
    </details>

    <details v-for="abilityKey in ['q', 'w', 'e', 'r']" :key="abilityKey">
      <summary class="text-lg font-semibold cursor-pointer uppercase">{{ abilityKey }} Ability</summary>
      <ChampionAbility :ability="champion?.[abilityKey]" :label="abilityKey.toUpperCase()" @update="onSectionUpdate(abilityKey, $event)" />
    </details>

    <!-- Validation and Save -->
    <div class="flex items-center gap-4">
      <label class="inline-flex items-center gap-2">
        <input type="checkbox" v-model="champion.validated" />
        <span>Validated</span>
      </label>
      <button class="bg-blue-600 text-white px-4 py-2 rounded shadow" @click="showConfirm = true">
        Save Changes
      </button>
    </div>

    <!-- Confirmation Modal -->
    <ModalConfirm
      v-if="showConfirm"
      @confirm="saveChampion"
      @cancel="showConfirm = false"
      :changes="changesToConfirm"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

import ChampionStats from './sections/ChampionStats.vue'
import ChampionPassive from './sections/ChampionPassive.vue'
import ChampionAbility from './sections/ChampionAbility.vue'
import ModalConfirm from './sections/ModalConfirm.vue'

const route = useRoute()
const champion = ref(null)
const showConfirm = ref(false)
const changesToConfirm = ref([])

onMounted(async () => {
  const { id } = route.params
  const { data } = await axios.get(`/champion/${id}`)
  champion.value = data
})

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}

function onSectionUpdate(section, changes) {
  if (!champion.value) return

  if (section === 'stats') {
    Object.assign(champion.value, changes)
  } else {
    Object.assign(champion.value[section], changes)
  }

  // Find existing entry
  const existing = changesToConfirm.value.find(c => c.section === section)
  if (existing) {
    Object.assign(existing.changes, changes)
  } else {
    changesToConfirm.value.push({ section, changes: { ...changes } })
  }
}

async function saveChampion() {
  await axios.put(`/champion/${champion.value.id}`, champion.value)
  showConfirm.value = false
  changesToConfirm.value = []
}
</script>

<style scoped>
details summary::-webkit-details-marker {
  display: none;
}
</style>