<template>
  <div class="min-h-screen flex flex-col bg-gray-100">
    <TopBar />
    <main class="flex-grow w-full px-4 py-6">
      <div class="flex max-w-7xl mx-auto">
        <aside class="w-16 lg:w-32 xl:w-48"></aside>
        <div class="flex-grow px-4">
          <router-view />
        </div>
        <aside class="w-16 lg:w-32 xl:w-48"></aside>
      </div>
    </main>
  </div>
</template>

<script setup>
import TopBar from './TopBar.vue'
</script>