import { createRouter, createWebHashHistory } from "vue-router";

import Patchloader from "./views/patchloader/Patchloader.vue";
import Dataoverview from "./views/dataoverview/Dataoverview.vue";
import Champion from "./views/editor/Champion.vue";
import Item from "./views/editor/Item.vue";
import Rune from "./views/editor/Rune.vue";
import Summonerspell from "./views/editor/Summonerspell.vue";



const router = createRouter({
    history: createWebHashHistory(),
    routes: [
        {
            path: "/",
            name: "patchloader",
            component: Patchloader
        },
        {
            path: "/data",
            name: "data",
            component: Dataoverview
        },
        {
            path: "/champion/:id",
            name: "champion",
            component: Champion
        },
        {
            path: "/item/:id",
            name: "item",
            component: Item
        },
        {
            path: "/rune/:id",
            name: "rune",
            component: Rune
        },
        {
            path: "/summonerspell/:id",
            name: "summonerspell",
            component: Summonerspell
        },
    ]
})


export default router;