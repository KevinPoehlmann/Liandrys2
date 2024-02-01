<script setup>
import { watch, inject } from 'vue';

const { passive } = defineProps(['passive']);
const URL = inject("URL");
const emit = defineEmits();

watch(passive, (newPassive) => {
  //console.log(newPassive)
  emit('update', newPassive);
});

</script>



<template>
  <div class="mb-6">
    <div class="flex items-center mb-2">
      <img
      :src="URL + 'images/' + passive.image.group + '/' + passive.image.full"
      :alt="passive.name"
      class="w-12 h-12 object-cover border border-black rounded-3xl mr-4"
      />
      <h3 class="text-gray-200 text-lg font-semibold">{{ passive.name }}</h3>
    </div>
    <div class="border border-white rounded-md p-4">
      <div class="flex flex-col mb-4">
        <label :for="description" class="text-gray-200  w-40 mb-1">Description:</label>
        <textarea 
          type="text" 
          :id="description" 
          :value="passive.description" 
          @input="updateValue" 
          class="form-input rounded w-3/5 overflow-auto p-2" 
          rows="3"
        ></textarea>
      </div>
      <div
      :class="{'bg-green-500': passive.ready_to_use, 'bg-red-400': !passive.ready_to_use}"
      class="mb-6 border border-white rounded-md w-40 p-2"
    >
      <label for="readyToUsePassive" class="flex items-center cursor-pointer">
        <span class="mr-2">Ready to Use:</span>
        <input
        type="checkbox"
        id="readyToUsePassive"
        v-model="passive.ready_to_use"
          class="form-checkbox h-5 w-5"
        />
      </label>
    </div>
    </div>
  </div>
</template>