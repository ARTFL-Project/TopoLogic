import Vue from "vue"
import App from "./App.vue"
import router from "./router"
import BootstrapVue from "bootstrap-vue"
import "bootstrap/dist/css/bootstrap.css"
import "bootstrap-vue/dist/bootstrap-vue.css"
import axios from "axios"
import VueApexCharts from "vue-apexcharts"
import modelConfig from "!raw-loader!../model_config.ini"

import globalConfig from "../appConfig.json"

Vue.config.productionTip = false
Vue.use(BootstrapVue)

Vue.use(VueApexCharts)
Vue.component("apexchart", VueApexCharts)

Vue.prototype.$http = axios
Vue.prototype.$globalConfig = globalConfig
Vue.prototype.$modelConfig = parseModelConfig()

new Vue({
    el: "#app",
    router,
    template: "<App/>",
    components: {
        App
    },
    render: h => h(App)
})

function parseModelConfig() {
    var regex = {
        section: /^\s*\[\s*([^\]]*)\s*\]\s*$/,
        param: /^\s*([^=]+?)\s*=\s*(.*?)\s*$/,
        comment: /^\s*;.*$/
    }
    var value = {}
    var lines = modelConfig.split(/[\r\n]+/)
    var section = null
    var match
    lines.forEach(function(line) {
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
        } else if (line.length == 0 && section) {
            section = null
        }
    })
    return value
}