import { createApp } from "vue"
import App from "./App.vue"
import router from "./router/index.js"
import axios from "axios"
import VueApexCharts from "vue3-apexcharts"

import "bootstrap/dist/css/bootstrap.css"
import "bootstrap"

import globalConfig from "../appConfig.json"
import modelConfigRaw from "../model_config.ini?raw"

const app = createApp(App)

app.use(router)
app.component("apexchart", VueApexCharts)

app.config.globalProperties.$http = axios
app.config.globalProperties.$globalConfig = globalConfig
app.config.globalProperties.$modelConfig = parseModelConfig(modelConfigRaw)

app.mount("#app")

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
