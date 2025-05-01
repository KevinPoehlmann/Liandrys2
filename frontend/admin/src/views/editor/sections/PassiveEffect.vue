<template>
  <div class="space-y-4">
    <h3 class="text-lg font-semibold">Effects</h3>

    <div v-for="(effect, index) in localEffects" :key="index" class="border rounded p-4 space-y-2">
      <div class="flex items-center gap-4">
        <label class="text-sm font-medium">Buff Type:</label>
        <select v-model="effect.buff" class="px-2 py-1 border rounded">
          <option v-for="buff in enums.buffs" :key="buff" :value="buff">{{ formatEnumLabel(buff.name) }}</option>
        </select>

        <button @click="removeEffect(index)" class="text-red-600 text-sm ml-auto">Remove</button>
      </div>

      <!-- Placeholder for props editing -->
      <StatProps
        v-if="effect.buff.value === 'Stats'"
        v-model="effect.props"
      />
      <ActionProps
        v-if="effect.buff.value === 'Cast'"
        v-model="effect.props"
      />
    </div>

    <button @click="addEffect" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
      + Add Effect
    </button>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import axios from 'axios'
import { formatEnumLabel } from '@/utils/formatters'
import StatProps from './StatProps.vue'
import ActionProps from './ActionProps.vue'

const props = defineProps({
  effects: Array
})
const emit = defineEmits(['update'])

const localEffects = ref([])
const enums = ref({ buffs: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.buffs = data.Buff
})

watch(localEffects, () => {
  const original = props.effects || []
  const current = localEffects.value

  if (JSON.stringify(original) !== JSON.stringify(current)) {
    emit('update', JSON.parse(JSON.stringify(current)))
  }
}, { deep: true })

watch(localEffects, () => {
  emit('update', JSON.parse(JSON.stringify(localEffects.value)))
}, { deep: true })

function addEffect() {
  localEffects.value.push({ buff: enums.value.buffs[0], props: {} })
}

function removeEffect(index) {
  localEffects.value.splice(index, 1)
}
</script>
