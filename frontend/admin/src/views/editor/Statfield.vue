<script setup>
const { label, value } = defineProps(['label', 'value'])
const emit = defineEmits();

const updateValue = ($event) => {
  console.log($event.target.value)
  emit('update', $event.target.value);
};
</script>

<template>
  <div class="flex flex-col">
    <label :for="label" class="text-gray-200  w-40 mb-1">{{ label }}:</label>
    <input type="number" :id="label" :value="value" @input="updateValue" class="form-input rounded-sm" />
  </div>
</template>