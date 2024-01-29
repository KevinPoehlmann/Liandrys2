<script setup>
import axios from 'axios'
import { ref, inject,  onBeforeMount } from 'vue';

const URL = inject("URL");
const status = ref("");
const patch = ref("4.20");
const todos = ref([]);


const get_status = () => {
  axios.get(`${URL}patch/status/`)
    .then((res) => {
      status.value = res.data.msg;
      console.log(res.data.todo)
      todos.value = res.data.todo;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      status.value = "Error"
    })
}

const update = () => {
  axios.post(`${URL}patch/`)
    .then((res) => {
      status.value = res.data.msg;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      status.value = "Error"
    })
}

const get_patch = () => {
  axios.get(`${URL}patch/`)
    .then((res) => {
      patch.value = res.data.patch;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      patch.value = "Error"
    })
}

onBeforeMount(() => {
  get_patch();
});
</script>



<template>
  <div class="container mx-auto p-8 dark:bg-gray-800">
    <div class="bg-white dark:bg-gray-700 p-8 rounded shadow-md">
      <h1 class="text-3xl font-semibold mb-4">Game Patch Updates</h1>

      <div class="mb-4">
        <p class="text-lg">{{ patch }}</p>
        <button
          type="button"
          @click="get_status()"
          class="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600 dark:hover:bg-blue-700"
        >
          Get Status
        </button>
      </div>

      <p class="text-lg">{{ status }}</p>

      <ul class="list-disc pl-4">
        <li v-for="todo in todos" :key="todo">
          <span class="text-green-500">{{ todo.todo_type }}</span> - {{ todo.patch }} - {{ todo.hotfix }}
        </li>
      </ul>

      <div class="mt-8">
        <button
          type="button"
          @click="update()"
          :disabled="todos.length === 0"
          class="bg-green-500 text-white py-2 px-4 rounded hover:bg-green-600 dark:hover:bg-green-700"
        >
          Load Updates
        </button>
      </div>
    </div>
  </div>
</template>

