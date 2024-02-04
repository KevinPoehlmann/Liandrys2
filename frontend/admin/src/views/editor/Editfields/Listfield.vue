<script setup>
const { label, value } = defineProps(['label', 'value']);
const emit = defineEmits();

const updateValue = (newValue) => {
  emit('update', newValue);
};

const addItem = () => {
  const newArray = [...value, '']; // Add an empty string as a new item
  updateValue(newArray);
};

const removeItem = (index) => {
  const newArray = [...value.slice(0, index), ...value.slice(index + 1)]; // Remove item at index
  updateValue(newArray);
};
</script>

<template>
  <div class="flex flex-col">
    <label class="text-gray-200 w-40 mb-1">{{ label }}</label>
    <div>
      <div v-for="(item, index) in value" :key="index" class="flex items-center mb-2">
        <input
          type="text"
          :value="item"
          @input="(e) => updateValue([...value.slice(0, index), e.target.value, ...value.slice(index + 1)])"
          class="form-input rounded-sm mr-2"
        />
        <button @click="removeItem(index)" class="text-red-500 hover:text-red-700">Remove</button>
      </div>
      <button @click="addItem" class="text-green-500 hover:text-green-700">Add Item</button>
    </div>
  </div>
</template>