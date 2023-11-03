<script setup>
import PatchLoader from './components/PatchLoader.vue'
import Logger from './components/Logger.vue';
</script>

<template>
  <div>
    <PatchLoader header="Liandrys Admin" />
    <Logger/>
  </div>
</template>

<style scoped>
.logo {
  height: 6em;
  padding: 1.5em;
  will-change: filter;
  transition: filter 300ms;
}
.logo:hover {
  filter: drop-shadow(0 0 2em #646cffaa);
}
.logo.vue:hover {
  filter: drop-shadow(0 0 2em #42b883aa);
}
</style>
