<script setup>
import axios from 'axios';
import { ref, inject, onBeforeMount, watch } from "vue";



const URL = inject("URL");

const patch = inject("patch")
const categories = ref([
        {
          id: 1,
          name: 'Champions',
          route: 'champion',
          items: [],
          filteredItems: [],
        },
        {
          id: 2,
          name: 'Items',
          route: 'item',
          items: [],
          filteredItems: [],
        },
        {
          id: 3,
          name: 'Runes',
          route: 'rune',
          items: [],
          filteredItems: [],
        },
        {
          id: 4,
          name: 'Summonerspells',
          route: 'summonerspell',
          items: [],
          filteredItems: [],
        },
        // Add more categories
      ])

const searchQuery = ref('');




onBeforeMount(() => {
  axios.get(`${URL}champion/all/${patch.value}`)
  .then((champs) => {
    categories.value[0].items = champs.data;
    categories.value[0].filteredItems = champs.data;
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
  axios.get(`${URL}item/all/${patch.value}`)
  .then((itemRes) => {
    categories.value[1].items = itemRes.data;
    categories.value[1].filteredItems = itemRes.data;
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
  axios.get(`${URL}rune/all/${patch.value}`)
  .then((runeRes) => {
    categories.value[2].items = runeRes.data;
    categories.value[2].filteredItems = runeRes.data;
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
  axios.get(`${URL}summonerspell/all/${patch.value}`)
  .then((summonerspellRes) => {
    categories.value[3].items = summonerspellRes.data;
    categories.value[3].filteredItems = summonerspellRes.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  }
)




watch(searchQuery, () => {
  for(const cat of categories.value) {
    cat.filteredItems = cat.items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.value.toLowerCase())
    );
  }
});


</script>


<template>
  <div class="p-8">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-2xl text-gray-200 font-semibold">Champion Selection:</h2>
      <input
        v-model="searchQuery" type="text" placeholder="Search..."
        class=" w-96 ml-4 p-2 border border-gray-300 rounded text-gray-800 focus:outline-none focus:border-blue-500"
      >
    </div>
    <div class="grid grid-cols-1 border border-white rounded-md p-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
      <div v-for="category in categories" :key="category.id">
        <h3 class="text-xl font-semibold text-gray-200 mb-2 ml-2">{{ category.name }}</h3>
        <ul class="border border-white rounded-md p-4 overflow-auto h-96">
          <li
            v-for="item in category.filteredItems" :key="item._id"
            >
            <router-link :to="`${category.route}/${item._id}`">
              <div :class="{ 'bg-green-700': item.ready_to_use, 'bg-red-700': !item.ready_to_use }"
              class="border border-white rounded p-1 hover:opacity-75 mb-1">
                <p class="text-gray-200 font-semibold">
                  {{ item.name }}
                </p>
              </div>
            </router-link>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>