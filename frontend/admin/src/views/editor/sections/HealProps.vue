<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium">Scaling</label>
      <input v-model="local.scaling" class="w-full px-2 py-1 border rounded" />
    </div>

    <div>
      <label class="block text-sm font-medium">HP Scaling</label>
      <select v-model="local.hp_scaling" class="w-full px-2 py-1 border rounded">
        <option v-for="h in enums.hpScaling" :key="h.value" :value="h.value">
          {{ formatEnumLabel(h.name) }}
        </option>
      </select>
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

const local = ref({ scaling: '', hp_scaling: '' })
const enums = ref({ hpScaling: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.hpScaling = data.HpScaling
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