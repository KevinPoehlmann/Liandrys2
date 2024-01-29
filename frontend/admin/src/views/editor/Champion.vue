<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";

const { params } = useRoute();
const URL = inject("URL");
const champion = ref({});


onBeforeMount(() => {
  axios.get(`${URL}champion/${params.id}`)
  .then((res) => {
    champion.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})
</script>


<template>
  <div>
    <h1>Champion</h1>
    <h3>{{ champion.name }}</h3>
  </div>
</template>