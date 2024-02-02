<script setup>
import axios from "axios";
import { getChanges, isEqual, deepCopy, updateValue } from "./helper.js"
import { ref, inject, onBeforeMount, watch } from "vue";
import { useRoute } from "vue-router";
import Statfield from "./Statfield.vue";
import Edited from "./Edited.vue";

const { params } = useRoute();
const URL = inject("URL");
const item = ref({});
const unchanged = ref({})
const changed = ref(false)
const mod = ref(false)


onBeforeMount(() => {
  axios.get(`${URL}item/${params.id}`)
  .then((res) => {
    item.value = res.data;
    unchanged.value = deepCopy(res.data);
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
})



watch(item, (newItem) => {
  changed.value = !isEqual(newItem, unchanged.value);
}, { deep: true })


const saveChanges = () => {
  console.log(item.value)
 axios.put(`${URL}item`, item.value)
  .then((res) => {
    unchanged.value = deepCopy(item.value)
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
        v-if="item.image && item.image.full"
        :src="URL + 'images/' + item.image.group + '/' + item.image.full"
        :alt="item.name"
        class="w-32 h-32 object-cover border-4 border-black rounded mr-4"
      />

      <!-- Item Details -->
      <div>
        <p class="text-gray-200 mb-1">DB:  {{ item._id }}</p>
        <h2 class="text-gray-200 text-2xl font-bold mb-2">{{ item.name }}</h2>
        <p class="text-gray-200 mb-1">ID:  {{ item.item_id }}</p>
      </div>
    </div>
    <!-- Stat Fields -->
    <h2 class="text-gray-200 text-xl font-semibold mb-3 ml-12">Stats</h2>
    <div class="border border-white rounded-md p-4 mb-6 flex flex-wrap gap-6">
      <div>
        <div>
          <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Base Stats</h3>
          <div v-if="item.stats" class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
            <Statfield
              v-for="[stat, value] in Object.entries(item.stats)" :key="stat"
              :label="stat" :value="value" @update="updateValue(item, `stats.${stat}`, $event)"
            /> 
          </div>
        </div>
      </div>
    </div>
    <!-- Switch for ready_to_use -->
    <div class="flex flex-wrap gap-6 mb-6">
      <div
      :class="{'bg-green-500': item.ready_to_use, 'bg-red-400': !item.ready_to_use}"
      class="mb-6 border border-white rounded-md w-40 p-2"
    >
      <label for="readyToUse" class="flex items-center cursor-pointer">
        <span class="mr-2">Ready to Use:</span>
        <input
        type="checkbox"
        id="readyToUse"
        v-model="item.ready_to_use"
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
    <Edited :mod="mod" :changes="getChanges(item, unchanged)" :pushChanges="saveChanges" :closeModal="cancelChanges"/>
  </div>
</template>