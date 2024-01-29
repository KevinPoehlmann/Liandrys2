<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";

const { params } = useRoute();
const URL = inject("URL");
const item = ref({});


onBeforeMount(() => {
  axios.get(`${URL}item/${params.id}`)
  .then((res) => {
    item.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})
</script>


<template>
  <div>
    <h1>Item</h1>
    <h3>{{ item.name }}</h3>
  </div>
</template>