<script setup>
import axios from "axios";
import { getChanges, isEqual, deepCopy, updateValue } from "./helper.js"
import { ref, inject, onBeforeMount, watch } from "vue";
import { useRoute } from "vue-router";
import Statfield from "./Editfields/Statfield.vue";
import Selectionfield from "./Editfields/Selectionfield.vue";
import Textfield from "./Editfields/Textfield.vue";
import ListField from "./ListField.vue";
import Multiselectionfield from "./Editfields/Multiselectionfield.vue"
import Edited from "./Edited.vue";

const { params } = useRoute();
const URL = inject("URL");
const item = ref({});
const unchanged = ref({})
const changed = ref(false)
const itemClasses = ref([]);
const maps = ref([]);
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
  axios.get(`${URL}item/itemclass/`)
  .then((res) => {
    itemClasses.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  axios.get(`${URL}item/map/`)
  .then((res) => {
    maps.value = res.data;
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
  <div v-if="item.name" class="p-8">
    <div class="flex items-center mb-8">
      <!-- Image -->
      <img
        :src="URL + 'images/' + item.image.group + '/' + item.image.full"
        :alt="item.name"
        class="w-32 h-32 object-cover border-4 border-black rounded mr-4"
      />

      <!-- Item Details -->
      <div>
        <p class="text-gray-200 font-semibold mb-1">DB:  {{ item._id }}</p>
        <h2 class="text-gray-200 text-2xl font-bold mb-2">{{ item.name }}</h2>
        <p class="text-gray-200 font-semibold mb-1">ID:  {{ item.item_id }}</p>
      </div>
    </div>
    <!-- Stat Fields -->
    <h2 class="text-gray-200 text-xl font-semibold mb-3 ml-12">Stats</h2>
    <div class="border border-white rounded-md p-4 mb-6 flex flex-wrap gap-6">
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Base Stats</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield
            v-for="[stat, value] in Object.entries(item.stats)" :key="stat"
            :label="stat" :value="value" @update="updateValue(item, `stats.${stat}`, $event)"
          />
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Build</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="Gold" :value="item.gold" @update="updateValue(item, 'gold', $event)" />
          <Selectionfield label="Class" :value="item.class_" :options="itemClasses" @update="updateValue(item, 'class_', $event)" />
          <ListField label="From" :value="item.from_" @update="updateValue(item, 'from_', $event)" />
          <ListField label="Into" :value="item.into" @update="updateValue(item, 'into', $event)" />
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Rules</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Textfield label="Limitations" :value="item.limitations" @update="updateValue(item, 'limitations', $event)" />
          <Textfield label="Requirements" :value="item.requirements" @update="updateValue(item, 'requirements', $event)" />
          <Multiselectionfield label="Maps" :value="item.maps" :options="maps" @update="updateValue(item, 'maps', $event)" />
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