import { createRouter, createWebHashHistory } from "vue-router";

import About from "./views/about/About.vue";
import Simulation from "./views/simulation/Simulation.vue";


const router = createRouter({
    history: createWebHashHistory(),
    routes: [
        {
            path: "/",
            name: "simulation",
            component: Simulation
        },
        {
            path: "/about",
            name: "about",
            component: About,
        }
    ]
})

export default router;