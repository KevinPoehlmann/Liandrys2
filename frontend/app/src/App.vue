<script setup>
import HelloWorld from './views/index/HelloWorld.vue'
import About from './views/about/About.vue';
import icon from "@/assets/Liandrys.png"

import { provide } from 'vue';

const URL = "http://127.0.0.1:5000/";
provide("URL", URL)



</script>

<template>
  <div>
    <header class="fixed top-0 w-full p-2 flex bg-teal-800 text-white">
      <ul class="flex">
        <li><router-link class="mx-1 p-2 bg-gray-900 hover:bg-gray-700" to="/">Home</router-link></li>
        <li><router-link class="mx-1 p-2 bg-gray-900 hover:bg-gray-700" to="/about">About</router-link></li>
      </ul>
      <div class="m-auto flex">
        <img :src="icon" alt="Liandrys" class="h-8 w-8"/>
        <h1 class="font-bold text-2xl text-center mx-2">Liandrys</h1>
      </div>
    </header>
    <div class="flex flex-row mt-12">
      <aside class="order-1 bg-green-900">Werbung</aside>
      <aside class="order-3 bg-green-900">Auch Werbung</aside>
      <router-view class="order-2 min-h-screen text-left bg-green-700"></router-view>
    </div>
    <footer class="sticky w-full bg-amber-600">Feet o.O</footer>
  </div>
</template>

