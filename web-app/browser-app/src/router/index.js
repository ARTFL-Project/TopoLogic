import Vue from 'vue'
import Router from 'vue-router'

import TopicDistributions from '../components/TopicDistributions'
import Topic from '../components/Topic'
import Document from '../components/Document'
import Word from '../components/Word'
import Vocabulary from '../components/Vocabulary'

Vue.use(Router)

export default new Router({
    mode: 'history',
    // base: '/',
    // base: globalConfig.appPath,
    routes: [{
            path: '/',
            name: 'home',
            component: TopicDistributions
        },
        {
            path: '/topic/:topic',
            name: 'topic',
            component: Topic
        },
        {
            path: '/document/:doc',
            name: 'document',
            component: Document
        },
        {
            path: '/word/:word',
            name: 'word',
            component: Word
        },
        {
            path: '/vocabulary',
            name: 'vocabulary',
            component: Vocabulary
        }
    ],
    scrollBehavior(to, from, savedPosition) {
        if (savedPosition) {
            return savedPosition
        } else {
            return {
                x: 0,
                y: 0
            }
        }
    }
})