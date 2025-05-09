<template>
  <div class="space-y-2">
    <Condition v-model="local.condition" />
    <label class="block text-sm font-medium">Stat</label>
    <select v-model="local.stat" class="w-full px-2 py-1 border rounded">
      <option v-for="s in enums.stats" :key="s.value" :value="s.value">
        {{ formatEnumLabel(s.name) }}
      </option>
    </select>

    <label class="block text-sm font-medium mt-2">Scaling</label>
    <input v-model="local.scaling" class="w-full px-2 py-1 border rounded" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { formatEnumLabel } from '@/utils/formatters'
import Condition from './Condition.vue'
import axios from 'axios'

const props = defineProps({
  modelValue: Object
})
const emit = defineEmits(['update:modelValue'])

const local = ref({ stat: '', scaling: '' })
const enums = ref({ stats: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.stats = data.Stat
})

watch(() => props.modelValue, (val) => {
  if (val) {
    local.value = { ...val }
  }
}, { immediate: true })

watch(local, () => {
  emit('update:modelValue', { ...local.value })
}, { deep: true })
</script>