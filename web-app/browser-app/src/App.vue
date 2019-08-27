<template>
    <div id="app">
        <b-navbar toggleable="lg" type="light" class="shadow-sm mb-4">
            <b-navbar-brand class="navbar-brand" to="/">Topic Model Browser</b-navbar-brand>
            <b-navbar-toggle target="nav-collapse"></b-navbar-toggle>
            <b-collapse class="mr-auto" id="nav-collapse" is-nav>
                <b-navbar-nav>
                    <b-nav-item-dropdown text="Navigate Topics" id="vocab-list">
                        <b-dropdown-item
                            v-for="topic in topicIds"
                            :key="topic"
                            :to="`/topic/${topic}`"
                        >Topic {{ topic }}</b-dropdown-item>
                    </b-nav-item-dropdown>
                    <b-nav-item to="/view/word">Vocabulary</b-nav-item>
                    <b-nav-item to="/view/author">Topics in Authors</b-nav-item>
                    <b-nav-item to="/time">Topics across Time</b-nav-item>
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
            topicIds: []
        };
    },
    created() {
        this.$http
            .get(
                `${this.$globalConfig.apiServer}/get_topic_ids?table=${this.$globalConfig.databaseName}`
            )
            .then(response => {
                this.topicIds = response.data;
            });
    }
};
</script>

<style>
#vocab-list .dropdown-menu {
    overflow: scroll;
    max-height: 440px;
}
section {
    font-family: OpenSans-Bold;
    font-size: 20px;
    line-height: 44px;
    color: #333333;
}

select {
    height: 30px;
    line-height: 40px;
    font-size: 12px;
    margin: auto;
    background-color: #fff;
}

button {
    height: 20px;
    line-height: 40px;
    font: 11px OpenSans;
    margin: auto;
}

#navigation {
    background-color: #444444;
    height: 40px;
    line-height: 40px;
}

#header {
    background-color: #333333;
    line-height: 40px;
}

#left_column {
    text-align: left;
    width: 600px;
    margin: 0 auto;
    float: left;
}

#five_columns {
    text-align: left;
    width: 200px;
    margin: 0 auto;
    float: left;
}

#three_columns {
    text-align: left;
    width: 333px;
    margin: 0 auto;
    float: left;
}

#one_column {
    text-align: left;
    width: 1000px;
    margin: 0 auto;
    float: left;
}

#right_column {
    text-align: left;
    width: 400px;
    margin: 0 auto;
    float: right;
}

.main-content {
    max-width: 900px;
    min-width: 900px;
    text-align: justify;
    margin: auto;
    padding: 5px;
}

a.class1 {
    font: 12px OpenSans-Bold;
}

a.class1:link {
    color: #444;
    text-decoration: none;
}

a.class1:visited {
    color: #444;
}

a.class1:hover {
    color: #55acee;
}

a.class2 {
    font: 11px OpenSans;
}

a.class2:link {
    color: #888;
    text-decoration: none;
}

a.class2:visited {
    color: #888;
}

a.class2:hover {
    color: #55acee;
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
