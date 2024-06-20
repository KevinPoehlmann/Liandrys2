<script setup>
import axios from "axios";
import icon from "@/assets/Liandrys.png"

import { provide, ref, onBeforeMount } from 'vue';

//const URL = "http://127.0.0.1:5000/";
const URL = "http://surfer:5000/";

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
    <header class="fixed top-0 w-full p-2 flex bg-teal-800 text-white">
      <ul class="flex mt-1">
        <li><router-link class="mx-1 p-2 bg-gray-900 rounded hover:bg-gray-700" to="/">Home</router-link></li>
        <li><router-link class="mx-1 p-2 bg-gray-900 rounded hover:bg-gray-700" to="/simulation">Simulation</router-link></li>
        <li><router-link class="mx-1 p-2 bg-gray-900 rounded hover:bg-gray-700" to="/about">About</router-link></li>
      </ul>
      <div class="m-auto flex">
        <img :src="icon" alt="Liandrys" class="h-8 w-8 rounded-full"/>
        <h1 class="font-bold text-2xl text-center mx-2">Liandrys</h1>
      </div>
      <div v-if="patch && allPatches[0]">
        <label for="patch" class="text-gray-200 w-40 mb-1">Patch: </label>
        <select id="patch" v-model="patch" class="form-select rounded-sm text-black">
          <option v-for="p in allPatches" :key="p" :value="p" class="text-black">{{ p }}</option>
        </select>
      </div>
    </header>
    <div class="flex flex-row mt-12">
      <aside class="order-1 bg-green-900">Supi</aside>
      <aside class="order-3 bg-green-900">Dupi</aside>
      <router-view v-if="patch" class="order-2 min-h-screen text-left bg-green-700 w-full p-8"></router-view>
    </div>
    <footer class="sticky w-full bg-amber-600">Feet o.O</footer>
  </div>
</template>

