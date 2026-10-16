<template>
  <div class="flex gap-2">
    <button
      v-for="option in options"
      :key="option"
      @click="$emit('update:modelValue', option)"
      :class="[
        'px-3 py-1 rounded border transition-colors duration-150',
        modelValue === option
          ? 'bg-blue-900 text-white border-blue-900'
          : 'bg-white dark:bg-gray-800 border-gray-400 text-gray-800 dark:text-gray-100'
      ]"
    >
      {{ option }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true
  },
  options: {
    type: Array,
    required: true
  }
})

defineEmits(['update:modelValue'])
</script>