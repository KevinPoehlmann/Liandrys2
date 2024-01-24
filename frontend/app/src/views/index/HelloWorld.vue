<script setup>
import { ref, inject } from 'vue';
import axios from "axios";


const URL = inject("URL");

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
    <div class="w-full p-8">  
      <div>
        <button class="p-2 m-1 bg-green-500 rounded-md hover:bg-green-400 active:border" type="button" @click="liandrys()">Send request</button>
        <p>
          {{ message }}
        </p>
      </div>
    </div>
</template>
