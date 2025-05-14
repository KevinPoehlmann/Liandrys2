<template>
  <header class="bg-white dark:bg-gray-800 shadow transition-colors duration-300">
    <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
      
      <!-- Left: Navigation -->
      <nav class="space-x-6">
        <RouterLink
          to="/"
          class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors duration-200"
        >
          Simulation
        </RouterLink>
        <RouterLink
          to="/about"
          class="text-gray-600 dark:text-gray-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors duration-200"
        >
          About
        </RouterLink>
      </nav>

      <!-- Center: Logo and Title -->
      <div class="absolute left-1/2 transform -translate-x-1/2 flex items-center space-x-3">
        <img :src="icon" alt="Liandrys Icon" class="h-10 w-10 rounded-full" />
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white">Liandrys2</h1>
      </div>

      <!-- Right: Theme Toggle -->
      <div class="w-24 flex justify-end">
        <button
          @click="toggleTheme"
          class="text-sm px-3 py-1 rounded bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-100 hover:bg-gray-300 dark:hover:bg-gray-600 transition"
        >
          Toggle
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import icon from '@/assets/Liandrys.png'

const toggleTheme = () => {
  const html = document.documentElement
  html.classList.toggle('dark')
}
</script>
