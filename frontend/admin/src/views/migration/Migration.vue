<template>
  <div class="p-6 space-y-4">
    <h1 class="text-2xl font-bold">Database Migration</h1>
    <div class="db-white p-4 rounded shadow">
      <div>
        <label><input type="checkbox" v-model="request.patch" /> Patch</label>
        <label><input type="checkbox" v-model="request.champion" /> Champion</label>
        <label><input type="checkbox" v-model="request.item" /> Item</label>
        <label><input type="checkbox" v-model="request.rune" /> Rune</label>
        <label><input type="checkbox" v-model="request.summonerspell" /> Summonerspell</label>
      </div>
      <button class="bg-red-700 text-white py-2 px-4 rounded" @click="confirmMigration">Migrate</button>
    </div>

    <div v-if="showConfirm" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white p-4 rounded shadow-xl">
        <h3 class="font-bold mb-2">Migrate Database?</h3>
        <p class="mb-4">This operation will modify existing data. Proceed?</p>
        <div class="flex justify-end space-x-2">
          <button class="bg-gray-200 px-4 py-1 rounded" @click="showConfirm = false">Cancel</button>
          <button class="bg-blue-600 text-white px-4 py-1 rounded" @click="runMigration">Confirm</button>
        </div>
      </div>
    </div>

    <div v-if="result">
      <h3 class="font-semibold mt-4">Result</h3>
      <pre>{{ result }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

const request = reactive({
  patch: false,
  champion: false,
  item: false,
  rune: false,
  summonerspell: false
});

const result = ref(null);
const showConfirm = ref(false);

function confirmMigration() {
  if (Object.values(request).some(Boolean)) {
    showConfirm.value = true;
  } else {
    alert("Please select at least one migration.");
  }
}

async function runMigration() {
  showConfirm.value = false;
  const res = await fetch("/admin/migration/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  result.value = await res.json();
}
</script>
