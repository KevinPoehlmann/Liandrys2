<template>
  <div class="min-h-screen flex flex-col bg-white text-black dark:bg-gray-900 dark:text-gray-100 transition-colors duration-300">
    <TopBar :is-dark="isDark" @toggle-theme="toggleTheme" />
    <main class="flex-grow w-full px-4 py-6 pt-20">
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
import { onMounted, ref } from 'vue'
import TopBar from './TopBar.vue'

const isDark = ref(false)

const toggleTheme = () => {
  const html = document.documentElement
  isDark.value = html.classList.toggle('dark')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  const stored = localStorage.getItem('theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  isDark.value = stored === 'dark' || (!stored && prefersDark)
  if (isDark.value) document.documentElement.classList.add('dark')
})
</script>
