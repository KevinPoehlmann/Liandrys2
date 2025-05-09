<template>
  <div v-if="rune" class="p-6 space-y-6">
    <h1 class="text-2xl font-bold">Rune Editor</h1>

    <!-- Top Info Block -->
    <div class="flex items-center gap-4">
      <img :src="imageUrl(rune?.image)" class="w-20 h-20 rounded shadow" />
      <div>
        <p><strong>Name:</strong> {{ rune?.name }}</p>
        <p><strong>Rune ID:</strong> {{ rune?.rune_id }}</p>
        <p><strong>ID:</strong> {{ rune?.id }}</p>
        <p><strong>Patch:</strong> {{ rune?.patch }}</p>
        <p><strong>Hotfix:</strong> {{ rune?.hotfix || '—' }}</p>
      </div>
    </div>

    <!-- Editable Fields -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label class="block text-sm font-medium mb-1">Tree</label>
        <input v-model="rune.tree" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">Tree ID</label>
        <input type="number" v-model.number="rune.tree_id" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">Row</label>
        <input type="number" v-model.number="rune.row" class="w-full px-2 py-1 border rounded" />
      </div>
    </div>

    <!-- Passive Section -->
    <details open>
      <summary class="text-lg font-semibold cursor-pointer">Passive</summary>
      <Passive :passive="rune.passive" />
    </details>

    <!-- Validation and Save -->
    <div class="flex items-center gap-4">
      <label class="inline-flex items-center gap-2">
        <input type="checkbox" v-model="rune.validated" />
        <span>Validated</span>
      </label>
      <button class="bg-blue-600 text-white px-4 py-2 rounded shadow" @click="showConfirm = true">
        Save Changes
      </button>
    </div>

    <!-- Confirmation Modal -->
    <ModalConfirm
      v-if="showConfirm"
      :current="rune"
      :original="originalRune"
      @confirm="saveRune"
      @cancel="showConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import ModalConfirm from './sections/ModalConfirm.vue'
import Passive from './sections/Passive.vue'

const route = useRoute()
const rune = ref(null)
const originalRune = ref(null)
const showConfirm = ref(false)

onMounted(async () => {
  const { id } = route.params
  const { data } = await axios.get(`/rune/${id}`)
  rune.value = JSON.parse(JSON.stringify(data))
  originalRune.value = JSON.parse(JSON.stringify(data))
})

async function saveRune() {
  await axios.put('/rune', rune.value)
  showConfirm.value = false
}

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}
</script>
