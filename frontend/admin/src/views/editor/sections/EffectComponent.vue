<template>
  <div class="space-y-4">
    <label class="text-sm font-medium">Effect Type</label>
    <select v-model="local.type_" class="w-full px-2 py-1 border rounded">
      <option v-for="e in enums.effectTypes" :key="e.value" :value="e.value">
        {{ formatEnumLabel(e.name) }}
      </option>
    </select>

    <DamageProps
      v-if="local.type_ === 'Damage'"
      v-model="local.props"
    />
    <HealProps
      v-if="local.type_ === 'Heal'"
      v-model="local.props"
    />
    <ShieldProps
      v-if="local.type_ === 'Shield'"
      v-model="local.props"
    />
    <StatusProps
      v-if="local.type_ === 'Status'"
      v-model="local.props"
    />

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
      <div>
        <label class="text-sm font-medium">Duration</label>
        <input type="number" step="0.1" v-model.number="local.duration" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="text-sm font-medium">Interval</label>
        <input type="number" step="0.1" v-model.number="local.interval" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="text-sm font-medium">Delay</label>
        <input type="number" step="0.1" v-model.number="local.delay" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="text-sm font-medium">Speed</label>
        <input type="number" v-model.number="local.speed" class="w-full px-2 py-1 border rounded" />
      </div>

      <div class="md:col-span-3">
        <label class="text-sm font-medium">Comment</label>
        <input v-model="local.comment" class="w-full px-2 py-1 border rounded" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import axios from 'axios'
import { formatEnumLabel } from '@/utils/formatters'
import DamageProps from './DamageProps.vue'
import HealProps from './HealProps.vue'
import ShieldProps from './ShieldProps.vue'
import StatusProps from './StatusProps.vue'



const props = defineProps({
  modelValue: Object
})
const emit = defineEmits(['update:modelValue'])

const local = ref({
  type_: '',
  props: {},
  duration: 0.0,
  interval: 0.0,
  delay: 0.0,
  speed: 0,
  comment: ''
})

const enums = ref({ effectTypes: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.effectTypes = data.EffectType
})

watch(() => props.modelValue, (val) => {
  if (!val) return

  local.value = {
    type_: '',
    props: {},
    duration: 0.0,
    interval: 0.0,
    delay: 0.0,
    speed: 0,
    comment: '',
    ...(val || {})
  }
}, { immediate: true })

watch(local, () => {
  const current = props.modelValue
  const next = { ...local.value }
  if (JSON.stringify(current) !== JSON.stringify(next)) {
    emit('update:modelValue', next)
  }
}, { deep: true })
</script>
