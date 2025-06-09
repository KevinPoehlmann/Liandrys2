<template>
  <div class="p-6 space-y-4">
    <h1 class="text-2xl font-bold">Patch Loader</h1>

    <!-- Current Patch Info -->
    <div class="bg-white p-4 rounded shadow">
      <h2 class="font-semibold text-lg">Current Patch</h2>
      <p>Patch: {{ currentPatch?.patch || "—" }}</p>
      <p>Hotfix: {{ currentPatch?.hotfix || "—" }}</p>
      <div v-if="patchLoadStatus === 'no-patch'" class="rounded-md bg-blue-100 p-4 text-blue-800 border border-blue-300">
        No patch loaded yet. Run the patch loader to begin.
      </div>

      <div v-if="patchLoadStatus === 'schema-error'" class="rounded-md bg-yellow-100 p-4 text-yellow-800 border border-yellow-300">
        Patch structure is outdated. Run the migration tool.
      </div>

      <div v-if="patchLoadStatus === 'unknown-error'" class="rounded-md bg-red-100 p-4 text-red-800 border border-red-300">
        Could not connect to the backend. Please check your setup.
      </div>
    </div>

    <!-- Available Updates -->
    <div class="bg-white p-4 rounded shadow">
      <h2 class="font-semibold text-lg">Available Updates</h2>
      <button @click="fetchAvailable" class="bg-blue-600 text-white py-2 px-4 rounded" :disabled="checking">
        {{ checking ? "Checking..." : "Check for Updates" }}
      </button>
      <div v-if="available && Object.keys(available).length > 0" class="mt-2">
        <ul class="list-disc ml-6">
          <li v-for="(hotfixes, patch) in available" :key="patch">
            <strong>{{ patch }}</strong> – Hotfixes: {{ hotfixes.join(', ') || "None" }}
          </li>
        </ul>
      </div>
      <p v-else-if="available">No updates available.</p>
    </div>

    <!-- Load Button -->
    <div>
      <button @click="loadPatch" class="bg-green-600 text-white py-2 px-4 rounded" :disabled="loading || !available || Object.keys(available).length === 0">
        {{ loading ? "Loading Patch..." : "Load New Patch" }}
      </button>
    </div>

    <!-- Load Log -->
    <div class="bg-gray-100 p-4 rounded shadow text-sm whitespace-pre-wrap">
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-semibold">Loader Log</h2>
        <button
          @click="fetchLog"
          class="bg-gray-800 text-white text-xs px-2 py-1 rounded hover:bg-gray-700"
        >
          Refresh
        </button>
      </div>

      <pre v-if="log"
        ref="logBox"
        class="bg-black text-green-400 p-2 rounded overflow-y-auto max-h-96"
      >
        {{ log }}
      </pre>
      <p v-else class="italic text-gray-500">No log content available yet.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import axios from 'axios'

const currentPatch = ref(null)
const patchLoadStatus = ref("")
const available = ref(null)
const loading = ref(false)
const checking = ref(false)
const log = ref("")
const logBox = ref(null)

onMounted(() => {
  fetchCurrentPatch()
  fetchLog()
})

async function fetchCurrentPatch() {
  try {
    const { data } = await axios.get("/patch/");
    currentPatch.value = data;
  } catch (err) {
    const status = err.response?.data?.status_code || err.message;

    if (status === 404) {
      patchLoadStatus.value = "no-patch";
    } else if (status === 422) {
      patchLoadStatus.value = "schema-error";
    } else {
      patchLoadStatus.value = "unknown-error";
    }

    console.warn("Patch load failed:", status);
    currentPatch.value = null;
  }
}

async function fetchAvailable() {
  checking.value = true
  const { data } = await axios.get("/patch/status")
  available.value = data.patches
  checking.value = false
}

async function loadPatch() {
  loading.value = true
  await axios.post("/admin/patch/")
  await fetchCurrentPatch()
  try {
    const logRes = await axios.get("/logs/patch_loader.log") // optional
    log.value = logRes.data
  } catch {
    log.value = "✅ Patch update triggered. Log file not available."
  }
  loading.value = false
}

async function fetchLog() {
  try {
    const res = await axios.get("/logs/patch_loader.log")
    log.value = res.data
  } catch (err) {
    log.value = "❌ Couldn't load log file."
  }
}

watch(log, () => {
  // Wait for DOM update
  nextTick(() => {
    if (logBox.value) {
      logBox.value.scrollTop = logBox.value.scrollHeight
    }
  })
})

</script>

