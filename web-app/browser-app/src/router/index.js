import Vue from 'vue'
import Router from 'vue-router'

import TopicDistributions from '../components/TopicDistributions'
import Topic from '../components/Topic'
import Document from '../components/Document'
import Word from '../components/Word'
import FieldView from '../components/FieldView'
import FieldDistribution from '../components/FieldDistribution'
import TimeView from '../components/TimeView'

import globalConfig from '../../appConfig.json'

Vue.use(Router)

export default new Router({
    mode: 'history',
    base: globalConfig.appPath,
    routes: [{
            path: '/',
            name: 'home'
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
            path: '/view/:fieldName',
            name: 'fieldView',
            component: FieldView
        },
        {
            path: '/metadata/:fieldName/:fieldValue',
            name: 'fieldDistribution',
            component: FieldDistribution
        },
        {
            path: '/time',
            name: 'time',
            component: TimeView
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