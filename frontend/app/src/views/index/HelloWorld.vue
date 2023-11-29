<script setup>
import { ref, inject } from 'vue';
import axios from "axios";
import ChampionsList from './ChampionsList.vue';


const URL = inject("URL");

const count = ref(0)
const message = ref("")


const liandrys = () => {
  axios.get(URL)
    .then((res) => {
      message.value = res.data.message;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      message.value = "Error"
    })
}
</script>

<template>
    <div>  
      <div>
        <button class="p-2 m-1 bg-green-500 rounded-md hover:bg-green-400 active:border" type="button" @click="liandrys()">Send request</button>
        <p>
          {{ message }}
        </p>
        <ChampionsList />
      </div>
    </div>
</template>
