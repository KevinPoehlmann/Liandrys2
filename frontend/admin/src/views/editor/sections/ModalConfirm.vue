<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg p-6 shadow-lg w-full max-w-xl">
      <h2 class="text-xl font-semibold mb-4">Confirm Changes</h2>

      <div v-if="Object.keys(diff).length">
        <ul class="list-disc pl-5 text-sm mb-4 space-y-1">
          <li v-for="(value, key) in diff" :key="key">
            <strong>{{ key }}:</strong>
            <pre class="bg-gray-100 rounded p-2 text-xs whitespace-pre-wrap">{{ JSON.stringify(value, null, 2) }}</pre>
          </li>
        </ul>
      </div>
      <p v-else class="text-sm italic text-gray-600 mb-4">No changes to confirm.</p>

      <div class="flex justify-end gap-4">
        <button @click="$emit('cancel')" class="px-4 py-2 rounded bg-gray-300 hover:bg-gray-400">
          Cancel
        </button>
        <button @click="$emit('confirm')" class="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700">
          Confirm & Save
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, toRaw } from 'vue'

const props = defineProps({
  current: Object,
  original: Object
})

function computeChanges(current, original) {
  const diff = {}

  function recursiveCompare(a, b, path = '', output = diff) {
    for (const key in a) {
      const fullKey = path ? `${path}.${key}` : key
      const aVal = toRaw(a[key])
      const bVal = toRaw(b?.[key])

      if (Array.isArray(aVal)) {
        const isPrimitiveArray = aVal.every(val =>
          ['string', 'number', 'boolean'].includes(typeof val)
        )

        if (isPrimitiveArray) {
          if (JSON.stringify(aVal) !== JSON.stringify(bVal)) {
            setNestedValue(output, fullKey, aVal)
          }
        } else {
          if (!Array.isArray(bVal) || aVal.length !== bVal.length) {
            setNestedValue(output, fullKey, aVal)
            continue
          }

          const arrayDiffs = []
          let hasChanges = false

          for (let i = 0; i < aVal.length; i++) {
            const subDiff = {}
            recursiveCompare(aVal[i], bVal[i], '', subDiff)
            if (Object.keys(subDiff).length) {
              arrayDiffs[i] = subDiff
              hasChanges = true
            } else {
              arrayDiffs[i] = null
            }
          }

          if (hasChanges) {
            setNestedValue(output, fullKey, arrayDiffs)
          }
        }
      }
 else if (typeof aVal === 'object' && aVal !== null) {
        const subOutput = {}
        recursiveCompare(aVal, bVal, fullKey, subOutput)
        if (Object.keys(subOutput).length) {
          setNestedValue(output, fullKey, subOutput)
        }
      } else if (aVal !== bVal) {
        setNestedValue(output, fullKey, aVal)
      }
    }
  }

  function setNestedValue(obj, path, value) {
    const keys = path.split('.')
    let current = obj
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {}
      current = current[keys[i]]
    }
    current[keys[keys.length - 1]] = value
  }

  recursiveCompare(current, original)
  return diff
}




const diff = computed(() => computeChanges(props.current, props.original))
</script>
