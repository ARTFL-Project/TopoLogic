import { createApp } from "vue"
import App from "./App.vue"
import router from "./router/index.js"
import axios from "axios"
import ECharts from "vue-echarts"
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { BarChart, LineChart } from "echarts/charts"
import {
    GridComponent,
    TooltipComponent,
    LegendComponent,
} from "echarts/components"

import "bootstrap/dist/css/bootstrap.css"
import "bootstrap"

import modelConfigRaw from "../model_config.ini?raw"

use([
    CanvasRenderer,
    BarChart,
    LineChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
])

// appConfig.json is fetched at runtime (not imported) so per-deployment edits
// — metadata fields, API URL, time-series bounds, etc. — take effect on page
// reload without rebuilding. Only appConfig.build.json (appPath) is baked in,
// because vite bakes `base` into asset URLs.
axios.get(`${import.meta.env.BASE_URL}appConfig.json`).then((response) => {
    const app = createApp(App)

    app.use(router)
    app.component("v-chart", ECharts)

    app.config.globalProperties.$http = axios
    app.config.globalProperties.$globalConfig = response.data
    app.config.globalProperties.$modelConfig = parseModelConfig(modelConfigRaw)

    app.mount("#app")
})

function parseModelConfig(raw) {
    const regex = {
        section: /^\s*\[\s*([^\]]*)\s*\]\s*$/,
        param: /^\s*([^=]+?)\s*=\s*(.*?)\s*$/,
        comment: /^\s*;.*$/
    }
    const value = {}
    const lines = raw.split(/[\r\n]+/)
    let section = null
    let match
    lines.forEach((line) => {
        if (regex.comment.test(line)) {
            return
        } else if (regex.param.test(line)) {
            match = line.match(regex.param)
            if (section) {
                value[section][match[1]] = match[2]
            } else {
                value[match[1]] = match[2]
            }
        } else if (regex.section.test(line)) {
            match = line.match(regex.section)
            value[match[1]] = {}
            section = match[1]
        } else if (line.length === 0 && section) {
            section = null
        }
    })
    return value
}
