<template>
    <div id="app">
        <b-navbar toggleable="lg" type="light" class="shadow-sm mb-4">
            <b-navbar-brand class="navbar-brand" to="/">Topic Model Browser</b-navbar-brand>
            <b-navbar-toggle target="nav-collapse"></b-navbar-toggle>
            <b-collapse class="mr-auto" id="nav-collapse" is-nav>
                <b-navbar-nav>
                    <b-nav-item-dropdown text="Navigate Topics" id="vocab-list">
                        <b-dropdown-item
                            v-for="topic in topicData"
                            :key="topic.name"
                            :to="`/topic/${topic.name}`"
                            class="pt-1 pb-1"
                        >Topic {{ topic.name }}: {{ topic.description }}</b-dropdown-item>
                    </b-nav-item-dropdown>
                    <b-nav-item to="/view/word">Vocabulary</b-nav-item>
                    <b-nav-item
                        v-for="field in metadataDistributions"
                        :key="field.field"
                        :to="`/view/${field.field}?filter=${field.filterFrequency}`"
                    >Topics in {{field.label}}s</b-nav-item>
                    <b-nav-item to="/time">Topics across Time</b-nav-item>
                </b-navbar-nav>
                <b-navbar-nav class="ml-auto">
                    <b-nav-form>
                        <b-input-group size="sm">
                            <b-form-input placeholder="Search for tokens" v-model="wordSelected"></b-form-input>
                            <b-input-group-append>
                                <b-button @click="searchVocab()">Search</b-button>
                            </b-input-group-append>
                        </b-input-group>
                    </b-nav-form>
                </b-navbar-nav>
            </b-collapse>
        </b-navbar>
        <model-statistics v-if="$route.name == 'home'"></model-statistics>
        <topic-distributions v-if="$route.name == 'home'" :topics="topicData"></topic-distributions>
        <router-view></router-view>
    </div>
</template>

<script>
import topics from "../topic_words.json";
import ModelStatistics from "./components/ModelStatistics";
import TopicDistributions from "./components/TopicDistributions";

export default {
    name: "app",
    components: { ModelStatistics, TopicDistributions },
    data() {
        return {
            topicData: topics,
            topicIds: [],
            metadataDistributions: this.$globalConfig.metadataDistributions,
            wordSelected: ""
        };
    },
    methods: {
        searchVocab() {
            this.$router.push(`/word/${this.wordSelected}`);
            this.wordSelected = "";
        }
    }
};
</script>

<style>
#vocab-list .dropdown-menu {
    overflow: scroll;
    max-height: 440px;
}
a:link {
    color: #55acee;
}

a:visited {
    color: #55acee;
}

a:hover {
    color: #000;
}

a:active {
    color: #55acee;
}
</style>
