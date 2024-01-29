<script setup>
import PatchLoader from './views/patchloader/PatchLoader.vue'
import Logger from './views/patchloader/Logger.vue';

import { provide } from 'vue';

const URL = "http://127.0.0.1:5001/";
provide("URL", URL)

</script>

<template>
  <div>
    <!-- Navigation Bar -->
    <nav class="bg-gray-800 p-4">
      <div class="container mx-auto flex items-center justify-between">
        <div class="space-x-4">
          <router-link to="/" class="text-white mx-1 p-2 bg-gray-800 hover:bg-gray-700">Patchloader</router-link>
          <router-link to="/data" class="text-white mx-1 p-2 bg-gray-800 hover:bg-gray-700">Data Overview</router-link>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <div class="bg-white dark:bg-gray-700 p-8 w-full min-h-screen">
      <!-- Your content goes here -->
      <h1 class="text-3xl font-semibold mb-4">Liandry's Admin</h1>
      <router-view></router-view>
    </div>
  </div>
</template>

