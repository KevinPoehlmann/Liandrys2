<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";

const { params } = useRoute();
const URL = inject("URL");
const summonerspell = ref({});


onBeforeMount(() => {
  axios.get(`${URL}summonerspell/${params.id}`)
  .then((res) => {
    summonerspell.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})
</script>


<template>
  <div>
    <h1>Summonerspell</h1>
    <h3>{{ summonerspell.name }}</h3>
  </div>
</template>