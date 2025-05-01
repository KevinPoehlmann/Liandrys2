<template>
  <header class="bg-white shadow">
    <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
      <!-- Left: Navigation -->
      <nav class="space-x-6">
        <RouterLink
          to="/simulation"
          class="text-gray-600 hover:text-indigo-600 transition-colors duration-200"
        >
          Simulation
        </RouterLink>
        <RouterLink
          to="/about"
          class="text-gray-600 hover:text-indigo-600 transition-colors duration-200"
        >
          About
        </RouterLink>
      </nav>

      <!-- Center: Logo and Title -->
      <div class="absolute left-1/2 transform -translate-x-1/2 flex items-center space-x-3">
        <img :src="icon" alt="Liandrys Icon" class="h-10 w-10 rounded-full" />
        <h1 class="text-2xl font-bold text-gray-800">Liandrys2</h1>
      </div>

      <!-- Right: empty placeholder to balance spacing -->
      <div class="w-24"></div>
    </div>
  </header>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import icon from '@/assets/Liandrys.png'
</script>