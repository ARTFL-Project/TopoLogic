<template>
    <b-container fluid class="mt-4">
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
                <b-row>
                    <b-col cols="12">
                        <b-card no-body class="shadow-sm">
                            <template v-slot:header>
                                <span class="mb-0">
                                    5 most important topics for
                                    <b>{{ word }}</b>
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
                                    <span class="frequency-value pl-2">{{ data.value }}%</span>
                                </template>
                            </b-table>
                        </b-card>
                    </b-col>
                </b-row>
                <b-row class="mt-4">
                    <b-col cols="6">
                        <b-card
                            no-body
                            :header="`${simWordsByTopics.length} most associated words by topic distribution`"
                        >
                            <b-list-group flush>
                                <b-list-group-item
                                    v-for="word in simWordsByTopics"
                                    :key="word.word"
                                    class="list-group-item"
                                    style="border-radius: 0px; border-width: 1px 0px; font-size: 90%"
                                >
                                    <a
                                        :id="`${word.word}-topics`"
                                        style="display:inline-block; cursor: pointer; color: #55acee"
                                    >{{ word.word }}</a>
                                    <word-link :target="`${word.word}-topics`" :word="word.word"></word-link>
                                    <b-badge variant="secondary" pill class="float-right">
                                        {{
                                        word.weight.toFixed(4)
                                        }}
                                    </b-badge>
                                </b-list-group-item>
                            </b-list-group>
                        </b-card>
                    </b-col>
                    <b-col cols="6">
                        <b-card
                            no-body
                            :header="`${simWordsByCooc.length} most associated words by document co-occurrence`"
                        >
                            <b-list-group flush>
                                <b-list-group-item
                                    v-for="word in simWordsByCooc"
                                    :key="word.word"
                                    class="list-group-item"
                                    style="border-radius: 0px; border-width: 1px 0px; font-size: 90%"
                                >
                                    <a
                                        :id="`${word.word}-docs`"
                                        style="display:inline-block; cursor: pointer; color: #55acee"
                                    >{{ word.word }}</a>
                                    <word-link :target="`${word.word}-docs`" :word="word.word"></word-link>
                                    <b-badge variant="secondary" pill class="float-right">
                                        {{
                                        word.weight.toFixed(4)
                                        }}
                                    </b-badge>
                                </b-list-group-item>
                            </b-list-group>
                        </b-card>
                    </b-col>
                </b-row>
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
                            <citations :doc="doc" :id="`${doc.doc_id}`"></citations>
                            <b-badge
                                variant="secondary"
                                pill
                                class="float-right"
                            >{{ doc.score.toFixed(2) }}</b-badge>
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
import WordLink from "./WordLink";

export default {
    name: "Word",
    components: { Citations, WordLink },
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
                joinedDistribution.push({
                    name: i,
                    frequency: topicDistribution.data[i].toFixed(3),
                    description: topicData[i].description
                });
            }
            joinedDistribution.sort(function(a, b) {
                return b.frequency - a.frequency;
            });
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
