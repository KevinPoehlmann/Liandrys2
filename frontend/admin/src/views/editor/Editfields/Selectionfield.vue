<script setup>
const { label, value, options } = defineProps(['label', 'value', 'options'])
const emit = defineEmits();

const updateValue = ($event) => {
  emit('update', $event.target.value);
};
</script>

<template>
  <div class="flex flex-col">
    <label :for="label" class="text-gray-200 w-40 mb-1">{{ label }}</label>
    <select :id="label" :value="value" @input="updateValue" class="form-select rounded-sm">
      <option v-for="op in options" :key="op" :value="op">{{ op }}</option>
    </select>
  </div>
</template>