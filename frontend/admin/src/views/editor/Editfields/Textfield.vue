<script setup>
const { label, value } = defineProps(['label', 'value'])
const emit = defineEmits();

const updateValue = ($event) => {
  emit('update', $event.target.value);
};
</script>

<template>
  <div class="flex flex-col">
    <label :for="label" class="text-gray-200  w-40 mb-1">{{ label }}:</label>
    <textarea 
      type="text" 
      :id="label" 
      :value="value" 
      @input="updateValue" 
      class="form-input rounded overflow-auto p-2" 
      rows="3"
    ></textarea>
  </div>
</template>