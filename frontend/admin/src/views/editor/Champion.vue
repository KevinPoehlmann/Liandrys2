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
      <ChampionStats :champion="champion" />
    </details>

    <details>
      <summary class="text-lg font-semibold cursor-pointer">Passive</summary>
      <Passive :passive="champion?.passive" show-image />
    </details>

    <details v-for="abilityKey in ['q', 'w', 'e', 'r']" :key="abilityKey">
      <summary class="text-lg font-semibold cursor-pointer uppercase">{{ abilityKey }} Ability</summary>
      <Ability :ability="champion?.[abilityKey]" show-image show-maxrank />
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
      :current="champion"
      :original="originalChampion"
      @confirm="saveChampion"
      @cancel="showConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

import Ability from './sections/Ability.vue'
import ChampionStats from './sections/ChampionStats.vue'
import ModalConfirm from './sections/ModalConfirm.vue'
import Passive from './sections/Passive.vue'

const route = useRoute()
const champion = ref(null)
const originalChampion = ref(null)
const showConfirm = ref(false)
const changesToConfirm = ref([])

onMounted(async () => {
  const { id } = route.params
  const { data } = await axios.get(`/champion/${id}`)
  champion.value = JSON.parse(JSON.stringify(data))
  originalChampion.value = JSON.parse(JSON.stringify(data))
})

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}


async function saveChampion() {
  await axios.put(`/admin/champion/`, champion.value)
  showConfirm.value = false
  changesToConfirm.value = []
}
</script>

<style scoped>
details summary::-webkit-details-marker {
  display: none;
}
</style>