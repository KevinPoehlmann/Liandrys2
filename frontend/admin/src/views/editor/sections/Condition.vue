<template>
  <div class="space-y-2">
    <label class="inline-flex items-center gap-2">
      <input type="checkbox" v-model="hasCondition" />
      <span>Condition enabled</span>
    </label>

    <div v-if="hasCondition" class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label class="text-sm font-medium">Key</label>
        <select v-model="local.key" class="w-full px-2 py-1 border rounded">
          <optgroup label="Stats">
            <option v-for="s in enums.stats" :key="s.value" :value="s.value">
              {{ formatEnumLabel(s.name) }}
            </option>
          </optgroup>
          <optgroup label="Actions">
            <option v-for="a in enums.actions" :key="a.value" :value="a.value">
              {{ formatEnumLabel(a.name) }}
            </option>
          </optgroup>
        </select>
      </div>

      <div>
        <label class="text-sm font-medium">Comparison</label>
        <select v-model="local.comparison" class="w-full px-2 py-1 border rounded">
          <option v-for="c in enums.comparisons" :key="c.value" :value="c.value">
            {{ formatEnumLabel(c.name) }}
          </option>
        </select>
      </div>

      <div>
        <label class="text-sm font-medium">Value</label>
        <input v-model.number="local.value" type="number" class="w-full px-2 py-1 border rounded" />
      </div>
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

const local = ref({ key: '', comparison: '', value: 0 })
const hasCondition = ref(false)
const enums = ref({ stats: [], actions: [], comparisons: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.stats = data.Stat
  enums.value.actions = data.ActionType
  enums.value.comparisons = data.Comparison
})

watch(() => props.modelValue, (val) => {
  if (val) {
    local.value = { ...val }
    hasCondition.value = true
  } else {
    hasCondition.value = false
  }
}, { immediate: true })

watch([local, hasCondition], () => {
  const current = props.modelValue
  const next = hasCondition.value ? { ...local.value } : null

  if (JSON.stringify(current) !== JSON.stringify(next)) {
    emit('update:modelValue', next)
  }
}, { deep: true })
</script>
