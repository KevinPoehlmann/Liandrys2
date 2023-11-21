<script setup>
import axios from 'axios'
import { ref, onBeforeMount } from 'vue'

const URL = "http://127.0.0.1:5000/";

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
  <div>
    <ul>
      <li v-for="champion in champions" :key="champion.key">
        <p>{{ champion.name }}</p>
      </li>
    </ul>
  </div>
</template>