<script setup>
import axios from 'axios';

import { ref } from 'vue'

const URL = "http://127.0.0.1:5001/";

const loader_log = ref("");

const get_log = () => {
  axios.get(`${URL}logs/patch_loader.log`)
    .then((res) => {
      console.log(res.data)
      loader_log.value = res.data;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      loader_log.value = "Error"
    })
}


</script>

<template>
  <div>
    <div class="card">
      <button type="button" @click="get_log()">Show Logs</button>
			<pre>{{ loader_log }}</pre>
    </div>
  </div>
</template>