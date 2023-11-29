<script setup>
import axios from "axios";
import { inject } from "vue";

defineProps({
  champion: Object,
})


const URL = inject("URL");
</script>


<template>
  <div class="m-1">
    <router-link :to="'/champion/' + champion._id">
      <div class="border-2 border-black hover:border-slate-200">
        <img :src="URL + 'images/' + champion.image.group + '/' + champion.image.full" :alt="champion.name"/>
        <p class="text-center bg-green-300">{{ champion.name }}</p>
      </div>
    </router-link>
  </div>
</template>