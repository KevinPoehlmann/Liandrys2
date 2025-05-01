<template>
  <div class="space-y-4">
    <Condition v-model="local.condition" />
    <!-- Triggers -->
    <div>
      <label class="block text-sm font-medium mb-1">Trigger(s)</label>
      <select v-model="local.trigger" multiple class="w-full px-2 py-1 border rounded h-24">
        <option v-for="a in enums.actions" :key="a.value" :value="a.value">
          {{ formatEnumLabel(a.name) }}
        </option>
      </select>
    </div>

    <!-- Buff Actions -->
    <div>
      <h4 class="font-semibold text-sm mb-1">Actions</h4>
      <div v-for="(action, index) in local.actions" :key="index" class="border rounded p-2 mb-2">
        <div class="flex items-center gap-4">
          <label class="text-sm">Type:</label>
          <select v-model="action.type_" class="px-2 py-1 border rounded">
            <option v-for="t in enums.buffActionTypes" :key="t.value" :value="t.value">
              {{ formatEnumLabel(t.name) }}
            </option>
          </select>
          <button @click="removeAction(index)" class="text-red-600 text-sm ml-auto">Remove</button>
        </div>
        <StackProps
          v-if="action.type_ === 'Stack'"
          v-model="action.props"
        />
        <EffectComponent
          v-if="action.type_ === 'Effect'"
          v-model="action.props"
        />
      </div>
      <button @click="addAction" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Action
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import axios from 'axios'
import { formatEnumLabel } from '@/utils/formatters'
import Condition from './Condition.vue'
import StackProps from './StackProps.vue'
import EffectComponent from './EffectComponent.vue'


const props = defineProps({
  modelValue: Object
})
const emit = defineEmits(['update:modelValue'])

const local = ref({ trigger: [], actions: [] })
const enums = ref({ actions: [], buffActionTypes: [] })

onMounted(async () => {
  const { data } = await axios.get('/enum/')
  enums.value.actions = data.ActionType
  enums.value.buffActionTypes = data.BuffActionType
})

watch(() => props.modelValue, (val) => {
  if (val) local.value = {
    ...val,
    trigger: Array.isArray(val.trigger) ? [...val.trigger] : [],
    actions: Array.isArray(val.actions) ? [...val.actions] : []
  }
}, { immediate: true })

watch(local, () => {
  const current = props.modelValue
  const next = { ...local.value }

  if (JSON.stringify(current) !== JSON.stringify(next)) {
    emit('update:modelValue', next)
  }
}, { deep: true })

function addAction() {
  local.value.actions.push({ type_: enums.value.buffActionTypes[0]?.value || '', props: {} })
}

function removeAction(index) {
  local.value.actions.splice(index, 1)
}
</script>
