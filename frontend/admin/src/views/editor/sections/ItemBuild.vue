<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <!-- From Section -->
    <div>
      <h3 class="font-semibold mb-2">Builds From</h3>
      <div v-for="(value, i) in from" :key="i" class="flex items-center gap-2 mb-2">
        <input v-model="from[i]" class="w-full px-2 py-1 border rounded" placeholder="Item ID..." />
        <button @click="removeFrom(i)" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addFrom" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add From
      </button>
    </div>

    <!-- Into Section -->
    <div>
      <h3 class="font-semibold mb-2">Builds Into</h3>
      <div v-for="(value, i) in into" :key="i" class="flex items-center gap-2 mb-2">
        <input v-model="into[i]" class="w-full px-2 py-1 border rounded" placeholder="Item ID..." />
        <button @click="removeInto(i)" class="text-red-600 font-semibold">✕</button>
      </div>
      <button @click="addInto" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        + Add Into
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  from: Array,
  into: Array
})

function addFrom() {
  props.from.push('')
}
function removeFrom(index) {
  props.from.splice(index, 1)
}

function addInto() {
  props.into.push('')
}
function removeInto(index) {
  props.into.splice(index, 1)
}
</script>
