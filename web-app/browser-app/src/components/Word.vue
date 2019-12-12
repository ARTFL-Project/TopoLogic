<template>
    <b-container fluid class="mt-4">
        <h5 class="text-center">
            Distribution of
            <b>{{ word }}</b> in the corpus
        </h5>
        <div v-if="notFound" class="p-4">
            <b>{{ word }}</b> not in vocabulary used for modeling.
            See
            <router-link to="/view/word">here</router-link>&nbsp;for available tokens
        </div>
        <div class="row mt-4 p-2" v-if="!notFound">
            <div class="col-7">
                <b-card no-body class="shadow-sm">
                    <template v-slot:header>
                        <span class="mb-0">
                            5 most important topics for
                            <b>{{word}}</b>
                        </span>
                    </template>
                    <b-table
                        hover
                        :items="topicDistribution"
                        :fields="fields"
                        @row-clicked="goToTopic"
                    >
                        <template slot="[name]" slot-scope="data">
                            <span class="frequency-parent">Topic {{ data.value }}</span>
                        </template>
                        <template slot="[description]" slot-scope="data">
                            <span class="frequency-parent">{{ data.value }}</span>
                        </template>
                        <template slot="[frequency]" slot-scope="data">
                            <span class="frequency-value pl-2">{{ data.value.toFixed(2) }}%</span>
                        </template>
                    </b-table>
                </b-card>
            </div>
            <div class="col-5">
                <b-card
                    no-body
                    class="shadow-sm"
                    :header="`Top ${documents.length} documents by relevance`"
                >
                    <b-list-group flush>
                        <b-list-group-item
                            v-for="doc in documents"
                            :key="doc.doc_id"
                            class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px; font-size: 90%"
                        >
                            <citations :doc="doc"></citations>
                            <b-badge
                                variant="secondary"
                                pill
                                class="float-right"
                            >{{doc.score.toFixed(2)}}</b-badge>
                        </b-list-group-item>
                    </b-list-group>
                </b-card>
            </div>
        </div>
    </b-container>
</template>
<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations";

export default {
    name: "Word",
    components: { Citations },
    data() {
        return {
            word: "",
            notFound: false,
            documents: [],
            topicDistribution: [],
            fields: [
                { key: "name", label: "Topic", sortable: false },
                { key: "description", label: "Top 10 tokens", sortable: false },
                {
                    key: "frequency",
                    label: "Word weight in topic",
                    sortable: false
                }
            ]
        };
    },
    mounted() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "loadNewData"
    },
    methods: {
        fetchData() {
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_word_data/${this.$globalConfig.databaseName}/${this.$route.params.word}`
                )
                .then(response => {
                    this.word = response.data.word;
                    this.documents = response.data.documents;
                    this.topicDistribution = this.build_topic_distribution(
                        response.data.topic_distribution
                    );
                })
                .catch(error => {
                    console.log(error);
                    this.word = this.$route.params.word;
                    this.notFound = true;
                });
        },
        build_topic_distribution(topicDistribution) {
            let joinedDistribution = [];
            for (let i = 0; i < topicData.length; i += 1) {
                joinedDistribution.push({
                    name: i,
                    frequency: topicDistribution.data[i],
                    description: topicData[i].description
                });
            }
            joinedDistribution.sort(function(a, b) {
                return b.frequency - a.frequency;
            });
            console.log(joinedDistribution.slice(0, 5));
            return joinedDistribution.slice(0, 5);
        },
        loadNewData() {
            this.fetchData();
        },
        goToTopic(topic) {
            this.$router.push(`/topic/${topic.name}`);
        }
    }
};
</script>