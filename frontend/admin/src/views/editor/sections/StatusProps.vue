<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium">Status Type</label>
      <select v-model="local.type_" class="w-full px-2 py-1 border rounded">
        <option v-for="s in enums.statusTypes" :key="s.value" :value="s.value">
          {{ formatEnumLabel(s.name) }}
        </option>
      </select>
    </div>

    <div>
      <label class="block text-sm font-medium">Duration</label>
      <input type="number" v-model.number="local.duration" class="w-full px-2 py-1 border rounded" />
    </div>

    <div>
      <label class="block text-sm font-medium">Strength</label>
      <input type="number" step="0.1" v-model.number="local.strength" class="w-full px-2 py-1 border rounded" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import axios from 'axios'
import { formatEnumLabel } from '@/utils/formatters'

const props = defineProps({
  modelValue: Object
})
const emit = defineEmits(['update:modelValue'])

const local = ref({ type_: '', duration: 0, strength: 0 })
const enums = ref({ statusTypes: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.statusTypes = data.StatusType
})

watch(() => props.modelValue, (val) => {
  if (val) local.value = { ...val }
}, { immediate: true })

watch(local, () => {
  const current = props.modelValue
  const next = { ...local.value }
  if (JSON.stringify(current) !== JSON.stringify(next)) {
    emit('update:modelValue', next)
  }
}, { deep: true })
</script>