<script setup>
import { ref } from 'vue';
import axios from "axios";

defineProps({
  msg: String,
})

const count = ref(0)
const message = ref("")

const URL = "http://127.0.0.1:5000/";

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
    <h1>{{ msg }}</h1>
    
    <div class="card">
      <button type="button" @click="liandrys()">Send request</button>
      <p>
        {{ message }}
      </p>
    </div>
  </div>
</template>
