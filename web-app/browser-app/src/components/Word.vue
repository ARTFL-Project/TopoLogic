<template>
    <div class="container-fluid mt-4">
        <h5 class="text-center">
            Distribution of
            <b>{{ word }}</b> in the corpus
        </h5>
        <div v-if="notFound" class="p-4">
            <b>{{ word }}</b> not in vocabulary used for modeling. See
            <router-link to="/view/word">here</router-link>&nbsp;for available tokens
        </div>
        <div class="row mt-4 p-2" v-if="!notFound">
            <div class="col-7">
                <div class="row">
                    <div class="col-12">
                        <div class="card shadow-sm">
                            <div class="card-header">
                                <span class="mb-0">
                                    Most important topics for
                                    <b>{{ word }}</b>
                                </span>
                            </div>
                            <sortable-table :items="topicDistribution" :fields="fields" @row-clicked="goToTopic">
                                <template v-slot:cell(name)="data">
                                    <span class="frequency-parent">Topic {{ data.value }}</span>
                                </template>
                                <template v-slot:cell(description)="data">
                                    <span class="frequency-parent">{{ data.value }}</span>
                                </template>
                                <template v-slot:cell(frequency)="data">
                                    <span class="frequency-value ps-2">{{ data.value }}%</span>
                                </template>
                            </sortable-table>
                        </div>
                    </div>
                </div>
                <div class="row mt-4">
                    <div class="col-6">
                        <div class="card">
                            <div class="card-header">{{ simWordsByTopics.length }} most associated words by topic distribution</div>
                            <ul class="list-group list-group-flush">
                                <li v-for="word in simWordsByTopics" :key="word.word"
                                    class="list-group-item"
                                    style="border-radius: 0px; border-width: 1px 0px; font-size: 90%">
                                    <a :id="`${word.word}-topics`"
                                        class="word-link">{{ word.word }}</a>
                                    <word-link :target="`${word.word}-topics`" :word="word.word"></word-link>
                                    <span class="badge rounded-pill bg-secondary float-end">
                                        {{ word.weight.toFixed(4) }}
                                    </span>
                                </li>
                            </ul>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="card">
                            <div class="card-header">{{ simWordsByCooc.length }} most associated words by document co-occurrence</div>
                            <ul class="list-group list-group-flush">
                                <li v-for="word in simWordsByCooc" :key="word.word"
                                    class="list-group-item"
                                    style="border-radius: 0px; border-width: 1px 0px; font-size: 90%">
                                    <a :id="`${word.word}-docs`"
                                        class="word-link">{{ word.word }}</a>
                                    <word-link :target="`${word.word}-docs`" :word="word.word"></word-link>
                                    <span class="badge rounded-pill bg-secondary float-end">
                                        {{ word.weight.toFixed(4) }}
                                    </span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-5">
                <div class="card shadow-sm">
                    <div class="card-header">Top {{ documents.length }} documents by relevance</div>
                    <ul class="list-group list-group-flush">
                        <li v-for="doc in documents" :key="doc.doc_id" class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px; font-size: 90%">
                            <citations :doc="doc" :id="`${doc.doc_id}`" :philo-db="`${doc.metadata.philo_db}`"></citations>
                            <span class="badge rounded-pill bg-secondary float-end">{{ doc.score.toFixed(2) }}</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations.vue";
import WordLink from "./WordLink.vue";
import SortableTable from "./SortableTable.vue";

export default {
    name: "Word",
    components: { Citations, WordLink, SortableTable },
    data() {
        return {
            word: "",
            notFound: false,
            documents: [],
            topicDistribution: [],
            simWordsByTopics: [],
            simWordsByCooc: [],
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
                    if (response.data.documents.length > 0) {
                        this.documents = response.data.documents;
                        this.topicDistribution = this.build_topic_distribution(
                            response.data.topic_distribution
                        );
                        this.simWordsByTopics =
                            response.data.similar_words_by_topic;
                        this.simWordsByCooc =
                            response.data.similar_words_by_cooc;
                        this.notFound = false;
                    } else {
                        this.notFound = true;
                    }
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
                let frequency = this.smartRound(topicDistribution.data[i])
                if (frequency == 0.0) {
                    continue;
                }
                joinedDistribution.push({
                    name: i,
                    frequency: this.smartRound(topicDistribution.data[i]),
                    description: topicData[i].description
                });
            }
            joinedDistribution.sort(function (a, b) {
                return b.frequency - a.frequency;
            });
            return joinedDistribution.slice(0, 5);
        },
        loadNewData() {
            this.fetchData();
        },
        goToTopic(topic) {
            this.$router.push(`/topic/${topic.name}`);
        },
        smartRound(num) {
            return num === 0 ? "0.00" : Number(Number(num).toPrecision(2)).toString();
        },
    }
};
</script>

<style scoped lang="scss">
@use "../assets/styles/theme.module.scss" as theme;

.word-link {
    display: inline-block;
    cursor: pointer;
    color: theme.$link-color;
}
</style>
