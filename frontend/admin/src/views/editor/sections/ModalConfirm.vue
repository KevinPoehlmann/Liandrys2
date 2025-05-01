<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg p-6 shadow-lg w-full max-w-lg">
      <h2 class="text-xl font-semibold mb-4">Confirm Changes</h2>

      <div v-if="changes.length">
        <ul class="list-disc pl-5 text-sm mb-4">
          <li v-for="(change, i) in changes" :key="i">
            <strong>{{ change.section }}:</strong>
            <pre class="bg-gray-100 rounded p-2 text-xs whitespace-pre-wrap">{{ JSON.stringify(change.changes, null, 2) }}</pre>
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
defineProps({
  changes: Array
})
</script>