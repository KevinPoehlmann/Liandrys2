<script setup>
import axios from "axios";
import { getChanges, isEqual, deepCopy, updateValue } from "./helper.js"
import { ref, inject, onBeforeMount, watch } from "vue";
import { useRoute } from "vue-router";
import Statfield from "./Statfield.vue";
import Edited from "./Edited.vue";

const { params } = useRoute();
const URL = inject("URL");
const rune = ref({});
const unchanged = ref({})
const changed = ref(false)
const mod = ref(false)


onBeforeMount(() => {
  axios.get(`${URL}rune/${params.id}`)
  .then((res) => {
    rune.value = res.data;
    unchanged.value = deepCopy(res.data);
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
})



watch(rune, (newRune) => {
  changed.value = !isEqual(newRune, unchanged.value);
}, { deep: true })


const saveChanges = () => {
  console.log(rune.value)
 axios.put(`${URL}rune`, rune.value)
  .then((res) => {
    unchanged.value = deepCopy(rune.value)
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
}

const cancelChanges = () => {
  mod.value = !mod.value
}


</script>


<template>
  <div class="p-8">
    <div class="flex items-center mb-8">
      <!-- Image -->
      <img
        v-if="rune.image && rune.image.full"
        :src="URL + 'images/' + rune.image.group + '/' + rune.image.full"
        :alt="rune.name"
        class="w-32 h-32 object-cover border-4 border-black rounded-full mr-4"
      />

      <!-- Rune Details -->
      <div>
        <p class="text-gray-200 mb-1">DB:  {{ rune._id }}</p>
        <h2 class="text-gray-200 text-2xl font-bold mb-2">{{ rune.name }}</h2>
        <p class="text-gray-200 mb-1">ID:  {{ rune.rune_id }}</p>
      </div>
    </div>
    <!-- Stat Fields -->
    <h2 class="text-gray-200 text-xl font-semibold mb-3 ml-12">Stats</h2>
    <div class="border border-white rounded-md p-4 mb-6 flex flex-wrap gap-6">
      <div>
        <div>
          <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Base Stats</h3>
          <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          </div>
        </div>
      </div>
    </div>
    <!-- Switch for ready_to_use -->
    <div class="flex flex-wrap gap-6 mb-6">
      <div
      :class="{'bg-green-500': rune.ready_to_use, 'bg-red-400': !rune.ready_to_use}"
      class="mb-6 border border-white rounded-md w-40 p-2"
    >
      <label for="readyToUse" class="flex items-center cursor-pointer">
        <span class="mr-2">Ready to Use:</span>
        <input
        type="checkbox"
        id="readyToUse"
        v-model="rune.ready_to_use"
          class="form-checkbox h-5 w-5"
        />
      </label>
    </div>
    </div>

    <!-- Save Changes Button -->
    <button
      @click="mod = !mod"
      :disabled="!changed"
      :class="{ 'opacity-50 cursor-not-allowed': !changed }"
      class="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
    >
      Save Changes
    </button>
    <Edited :mod="mod" :changes="getChanges(rune, unchanged)" :pushChanges="saveChanges" :closeModal="cancelChanges"/>
  </div>
</template>