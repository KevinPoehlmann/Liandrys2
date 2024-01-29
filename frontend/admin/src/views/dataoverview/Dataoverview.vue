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
    <h2 class="text-2xl font-semibold mb-4">Overview</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
      <div v-for="category in categories" :key="category.id">
        <h3 class="text-xl font-semibold mb-2">{{ category.name }}</h3>
        <ul>
          <li v-for="item in category.items" :key="item._id" :class="{ 'text-green-500': item.ready_to_use, 'text-red-500': !item.ready_to_use }">
            <router-link :to="`${category.route}/${item._id}`">{{ item.name }}</router-link>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>