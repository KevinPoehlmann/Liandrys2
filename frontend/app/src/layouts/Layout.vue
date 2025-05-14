<template>
  <div class="min-h-screen flex flex-col bg-white text-black dark:bg-gray-900 dark:text-gray-100 transition-colors duration-300">
    <TopBar @toggle-theme="toggleTheme" />
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

const toggleTheme = () => {
  const html = document.documentElement
  html.classList.toggle('dark')
}
</script>
