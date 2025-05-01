<template>
  <div class="space-y-3">
    <div>
      <label class="block text-sm font-medium">Scaling</label>
      <input v-model="local.scaling" class="w-full px-2 py-1 border rounded" />
    </div>

    <div>
      <label class="block text-sm font-medium">Damage Type</label>
      <select v-model="local.dmg_type" class="w-full px-2 py-1 border rounded">
        <option v-for="d in enums.dmgTypes" :key="d.value" :value="d.value">
          {{ formatEnumLabel(d.name) }}
        </option>
      </select>
    </div>

    <div>
      <label class="block text-sm font-medium">Damage Subtype</label>
      <select v-model="local.dmg_sub_type" class="w-full px-2 py-1 border rounded">
        <option v-for="s in enums.dmgSubTypes" :key="s.value" :value="s.value">
          {{ formatEnumLabel(s.name) }}
        </option>
      </select>
    </div>

    <div>
      <label class="block text-sm font-medium">HP Scaling</label>
      <select v-model="local.hp_scaling" class="w-full px-2 py-1 border rounded">
        <option v-for="h in enums.hpScaling" :key="h.value" :value="h.value">
          {{ formatEnumLabel(h.name) }}
        </option>
      </select>
    </div>

    <div>
      <label class="block text-sm font-medium">Vamp</label>
      <input type="number" v-model.number="local.vamp" class="w-full px-2 py-1 border rounded" />
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

const local = ref({
  scaling: '',
  dmg_type: '',
  dmg_sub_type: '',
  hp_scaling: '',
  vamp: 0
})

const enums = ref({ dmgTypes: [], dmgSubTypes: [], hpScaling: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.dmgTypes = data.DamageType
  enums.value.dmgSubTypes = data.DamageSubType
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
