<script setup>
import axios from "axios";

import { provide, ref, onBeforeMount } from 'vue';

//const URL = "http://127.0.0.1:5001/";
const URL = "http://surfer:5001/";

provide("URL", URL)

const patch = ref("")
provide("patch", patch)
const allPatches = ref([])

onBeforeMount(() => {
  axios.get(`${URL}patch/`)
  .then((res) => {
    patch.value = res.data.patch;
    console.log(patch.value)
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  axios.get(`${URL}patch/all/`)
  .then((res) => {
    allPatches.value = res.data.map((p) => p.patch);
    console.log(allPatches.value)
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})

</script>

<template>
  <div>
    <!-- Navigation Bar -->
    <nav class="bg-gray-800 p-4">
      <div class="container mx-auto flex items-center justify-between">
        <div class="space-x-4">
          <router-link to="/" class="text-white mx-1 p-2 bg-gray-800 rounded-md hover:bg-gray-700">Patchloader</router-link>
          <router-link to="/data" class="text-white mx-1 p-2 bg-gray-800 rounded-md hover:bg-gray-700">Data Overview</router-link>
        </div>
        <div>
          <h1 class="text-3xl font-bold text-gray-200 mb-4">Liandry's Admin</h1>
        </div>
        <div v-if="patch && allPatches[0]">
        <label for="patch" class="text-gray-200 w-40 mb-1">Patch: </label>
        <select id="patch" v-model="patch" class="form-select rounded-sm text-black">
          <option v-for="p in allPatches" :key="p" :value="p" class="text-black">{{ p }}</option>
        </select>
      </div>
      </div>
    </nav>

    <!-- Main Content -->
    <div class="bg-white dark:bg-gray-700 p-8 w-full min-h-screen">
      <!-- Your content goes here -->
      <router-view v-if="patch"></router-view>
    </div>
  </div>
</template>

