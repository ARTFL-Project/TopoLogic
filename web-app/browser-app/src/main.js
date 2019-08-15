import Vue from 'vue'
import App from './App.vue'
import router from './router'
import BootstrapVue from 'bootstrap-vue'
import 'bootstrap/dist/css/bootstrap.css'
import 'bootstrap-vue/dist/bootstrap-vue.css'
import axios from 'axios'

import globalConfig from "../appConfig.json";

Vue.config.productionTip = false
Vue.use(BootstrapVue)
Vue.prototype.$http = axios
Vue.prototype.$globalConfig = globalConfig

new Vue({
    el: '#app',
    router,
    template: '<App/>',
    components: {
        App
    },
    render: (h) => h(App)
})