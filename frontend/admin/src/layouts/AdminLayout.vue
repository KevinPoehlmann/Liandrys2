<template>
  <div class="flex h-screen bg-gray-100 text-gray-900">
    <!-- Sidebar -->
    <aside class="w-64 bg-white border-r shadow-sm p-4">
      <h1 class="text-2xl font-bold mb-6">Liandrys Admin</h1>
      <nav class="space-y-2">
        <router-link to="/" class="block px-2 py-1 rounded hover:bg-gray-100">Patch Loader</router-link>
        <router-link to="/data" class="block px-2 py-1 rounded hover:bg-gray-100">Data Overview</router-link>
      </nav>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-y-auto p-6">
      <slot />
    </main>
  </div>
</template>

<script setup>
</script>
