<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";

const { params } = useRoute();
const URL = inject("URL");
const rune = ref({});


onBeforeMount(() => {
  axios.get(`${URL}rune/${params.id}`)
  .then((res) => {
    rune.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})
</script>


<template>
  <div>
    <h1>Rune</h1>
    <h3>{{ rune.name }}</h3>
  </div>
</template>