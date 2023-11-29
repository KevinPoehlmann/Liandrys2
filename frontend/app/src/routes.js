import { createRouter, createWebHashHistory } from "vue-router";

import About from "./views/about/About.vue";
import HelloWorld from "./views/index/HelloWorld.vue";
import Champion from "./views/champion/Champion.vue";


const router = createRouter({
    history: createWebHashHistory(),
    routes: [
        {
            path: "/",
            name: "index",
            component: HelloWorld
        },
        {
            path: "/about",
            name: "about",
            component: About,
        },
        {
            path: "/champion/:id",
            name: "champion",
            component: Champion,
        }
    ]
})

export default router;