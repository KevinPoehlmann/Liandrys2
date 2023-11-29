<script setup>
import axios from 'axios'
import { ref, onBeforeMount, inject } from 'vue'
import ChampionCard from './ChampionCard.vue';

const URL = inject("URL");

const patch = ref("");
const champions = ref([]);


onBeforeMount(() => {
  axios.get(`${URL}patch/`)
    .then((res) => {
      patch.value = res.data.patch;
      if (patch.value) {
        console.log("Hi this is patch: " + patch.value)
        axios.get(`${URL}champion/all/${patch.value}`)
          .then((res) => {
            champions.value = res.data;
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
    <ul class="flex flex-row flex-wrap">
      <li v-for="champion in champions" :key="champion.key" class="m-auto">
        <ChampionCard :champion="champion"/>
      </li>
    </ul>
  </div>
</template>