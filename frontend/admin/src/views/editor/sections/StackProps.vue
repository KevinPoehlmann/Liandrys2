<template>
  <div class="space-y-2">
    <label class="text-sm font-medium">Stack Key</label>
    <select v-model="local.stack_key" class="w-full px-2 py-1 border rounded">
      <option v-for="a in enums.actions" :key="a.value" :value="a.value">
        {{ formatEnumLabel(a.name) }}
      </option>
    </select>

    <label class="text-sm font-medium mt-2">Amount</label>
    <input v-model="local.amount" class="w-full px-2 py-1 border rounded" />
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

const local = ref({ stack_key: '', amount: '' })
const enums = ref({ actions: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.actions = data.ActionType
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
