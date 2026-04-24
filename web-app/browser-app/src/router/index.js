import { createRouter, createWebHistory } from "vue-router"

import Topic from "../components/Topic.vue"
import Document from "../components/Document.vue"
import Word from "../components/Word.vue"
import FieldView from "../components/FieldView.vue"
import FieldDistribution from "../components/FieldDistribution.vue"
import TimeView from "../components/TimeView.vue"
import TopicalReading from "../components/TopicalReading.vue"
import MetadataExplorer from "../components/MetadataExplorer.vue"

import buildConfig from "../../appConfig.build.json"

export default createRouter({
    history: createWebHistory(buildConfig.appPath),
    routes: [
        { path: "/", name: "home", component: { render: () => null } },
        { path: "/topic/:topic", name: "topic", component: Topic },
        { path: "/document/:philoDb/:doc([\\d/]+)", name: "document", component: Document },
        { path: "/word/:word", name: "word", component: Word },
        { path: "/view/:fieldName", name: "fieldView", component: FieldView },
        { path: "/metadata/:fieldName/:fieldValue", name: "fieldDistribution", component: FieldDistribution },
        { path: "/time", name: "time", component: TimeView },
        { path: "/explorer", name: "explorer", component: MetadataExplorer },
        { path: "/explorer/:field", name: "explorerField", component: MetadataExplorer },
        {
            path: "/reading/:philoDb/:doc([\\d/]+)",
            name: "topicalReading",
            component: TopicalReading,
        },
    ],
    scrollBehavior(to, from, savedPosition) {
        return savedPosition || { top: 0 }
    },
})
