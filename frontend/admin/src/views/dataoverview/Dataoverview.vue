<script setup>
import axios from 'axios';
import { ref, inject, onBeforeMount } from "vue";



const URL = inject("URL");

const patch = ref("")
const categories = ref([
        {
          id: 1,
          name: 'Champions',
          route: 'champion',
          items: [],
        },
        {
          id: 2,
          name: 'Items',
          route: 'item',
          items: [],
        },
        {
          id: 2,
          name: 'Runes',
          route: 'rune',
          items: [],
        },
        {
          id: 2,
          name: 'Summonerspells',
          route: 'summonerspell',
          items: [],
        },
        // Add more categories
      ])
const champions = ref([])
const items = ref([])
const runes = ref([])
const summonerspells = ref([])


onBeforeMount(() => {
  axios.get(`${URL}patch/`)
  .then((res) => {
    patch.value = res.data.patch;
    if (patch.value) {
      axios.get(`${URL}champion/all/${patch.value}`)
      .then((champs) => {
        categories.value[0].items = champs.data;
      })
      .catch((error) => {
        console.error(`Error: ${error}`)
      })
      axios.get(`${URL}item/all/${patch.value}`)
      .then((itemRes) => {
        categories.value[1].items = itemRes.data;
      })
      .catch((error) => {
        console.error(`Error: ${error}`)
      })
      axios.get(`${URL}rune/all/${patch.value}`)
      .then((runeRes) => {
        categories.value[2].items = runeRes.data;
      })
      .catch((error) => {
        console.error(`Error: ${error}`)
      })
      axios.get(`${URL}summonerspell/all/${patch.value}`)
      .then((summonerspellRes) => {
        categories.value[3].items = summonerspellRes.data;
      })
      .catch((error) => {
        console.error(`Error: ${error}`)
      })
    }
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
      patch.value = "Error"
    })
})


</script>


<template>
  <div class="p-8">
    <h2 class="text-2xl font-semibold text-gray-200 mb-4">Overview</h2>
    <div class="grid grid-cols-1 border border-white rounded-md p-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
      <div v-for="category in categories" :key="category.id">
        <h3 class="text-xl font-semibold text-gray-200 mb-2 ml-2">{{ category.name }}</h3>
        <ul class="border border-white rounded-md p-4 overflow-auto h-96">
          <li
            v-for="item in category.items" :key="item._id"
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