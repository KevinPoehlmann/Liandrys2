<script setup>
import { ref } from 'vue';
const { label, value, options } = defineProps(['label', 'value', 'options']);
const emit = defineEmits();

const val = ref(value)

const updateValue = (selectedOptions) => {
  emit('update', selectedOptions);
};
</script>

<template>
  <div class="flex flex-col">
    <label :for="label" class="text-gray-200 w-40 mb-1">{{ label }}</label>
    <select
      :id="label"
      v-model="val"
      @change="updateValue(val)"
      multiple
      class="form-select rounded-sm"
    >
      <option v-for="opt in options" :key="opt" :value="opt">{{ opt }}</option>
    </select>
  </div>
</template>