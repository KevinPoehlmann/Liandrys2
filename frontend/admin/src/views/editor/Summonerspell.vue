<template>
  <div v-if="summoner" class="p-6 space-y-6">
    <h1 class="text-2xl font-bold">Summoner Spell Editor</h1>

    <!-- Top Info Block -->
    <div class="flex items-center gap-4">
      <img :src="imageUrl(summoner?.image)" class="w-20 h-20 rounded shadow" />
      <div>
        <p><strong>Name:</strong> {{ summoner?.name }}</p>
        <p><strong>Key:</strong> {{ summoner?.key }}</p>
        <p><strong>ID:</strong> {{ summoner?.id }}</p>
        <p><strong>Patch:</strong> {{ summoner?.patch }}</p>
        <p><strong>Hotfix:</strong> {{ summoner?.hotfix || '—' }}</p>
      </div>
    </div>

    <!-- Ability section placeholder -->
    <details open>
      <summary class="text-lg font-semibold cursor-pointer">Ability</summary>
      <Ability :ability="summoner.ability" />
    </details>

    <!-- Validation and Save -->
    <div class="flex items-center gap-4">
      <label class="inline-flex items-center gap-2">
        <input type="checkbox" v-model="summoner.validated" />
        <span>Validated</span>
      </label>
      <button class="bg-blue-600 text-white px-4 py-2 rounded shadow" @click="showConfirm = true">
        Save Changes
      </button>
    </div>

    <!-- Confirmation Modal -->
    <ModalConfirm
      v-if="showConfirm"
      :current="summoner"
      :original="originalSummoner"
      @confirm="saveSummoner"
      @cancel="showConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

import Ability from './sections/Ability.vue'
import ModalConfirm from './sections/ModalConfirm.vue'

const route = useRoute()
const summoner = ref(null)
const originalSummoner = ref(null)
const showConfirm = ref(false)

onMounted(async () => {
  const { id } = route.params
  const { data } = await axios.get(`/summonerspell/${id}`)
  summoner.value = JSON.parse(JSON.stringify(data))
  originalSummoner.value = JSON.parse(JSON.stringify(data))
})

async function saveSummoner() {
  await axios.put('/admin/summonerspell', summoner.value)
  showConfirm.value = false
}

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}
</script>
