<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";

const { params } = useRoute();
const URL = inject("URL");
const summonerspell = ref({});


onBeforeMount(() => {
  axios.get(`${URL}summonerspell/${params.id}`)
  .then((res) => {
    summonerspell.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})


const saveChanges = () => {
  console.log(summonerspell.value)
 axios.put(`${URL}summonerspell`, summonerspell.value)
  .then((res) => {
      console.log(res.data);
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
}


</script>


<template>
  <div class="p-8">
    <div class="flex items-center mb-8">
      <!-- Image -->
      <img
        v-if="summonerspell.image && summonerspell.image.full"
        :src="URL + 'images/' + summonerspell.image.group + '/' + summonerspell.image.full"
        :alt="summonerspell.name"
        class="w-32 h-32 object-cover rounded mr-4"
      />

      <!-- Item Details -->
      <div>
        <p class="text-gray-200 mb-1">DB:  {{ summonerspell._id }}</p>
        <h2 class="text-2xl font-semibold mb-2">{{ summonerspell.name }}</h2>
        <p class="text-gray-200 mb-1">Key:  {{ summonerspell.key }}</p>
      </div>
    </div>

    <!-- Switch for ready_to_use -->
    <div class="mb-6">
      <label for="readyToUse" class="flex items-center cursor-pointer">
        <span class="mr-2">Ready to Use:</span>
        <input
          type="checkbox"
          id="readyToUse"
          v-model="summonerspell.ready_to_use"
          class="form-checkbox h-5 w-5 text-green-500"
        />
      </label>
    </div>

    <!-- Save Changes Button -->
    <button
      @click="saveChanges"
      class="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
    >
      Save Changes
    </button>
  </div>
</template>