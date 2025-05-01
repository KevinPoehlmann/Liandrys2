<template>
  <div class="space-y-4 border rounded p-4">
    <div>
      <label class="block text-sm font-medium">Effect Text</label>
      <textarea v-model="local.text" rows="2" class="w-full px-2 py-1 border rounded" />
    </div>

    <div class="space-y-2">
      <label class="block text-sm font-medium">Effect Components</label>
      <div v-for="(comp, i) in local.effect_components" :key="i" class="p-2 rounded bg-gray-50 border">
        <EffectComponent v-model="local.effect_components[i]" />
        <button @click="removeComponent(i)" class="text-sm text-red-600 mt-1">Remove</button>
      </div>
      <button @click="addComponent" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Component
      </button>
    </div>

    <div>
      <label class="block text-sm font-medium">Conditions</label>
      <div class="space-y-2">
        <Condition
          v-for="(cond, i) in local.conditions"
          :key="i"
          v-model="local.conditions[i]"
        />
        <button @click="addCondition" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
          + Add Condition
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import EffectComponent from './EffectComponent.vue'
import Condition from './Condition.vue'

const props = defineProps({
  modelValue: Object
})
const emit = defineEmits(['update:modelValue'])

const local = ref({ text: '', effect_components: [], conditions: [] })

watch(() => props.modelValue, (val) => {
  if (val) local.value = { ...val, effect_components: [...val.effect_components], conditions: [...val.conditions] }
}, { immediate: true })

watch(local, () => {
  const current = props.modelValue
  const next = { ...local.value }
  if (JSON.stringify(current) !== JSON.stringify(next)) {
    emit('update:modelValue', next)
  }
}, { deep: true })

function addComponent() {
  local.value.effect_components.push({ type_: '', props: {} })
}

function removeComponent(index) {
  local.value.effect_components.splice(index, 1)
}

function addCondition() {
  local.value.conditions.push({ key: '', comparison: '', value: 0 })
}
</script>
