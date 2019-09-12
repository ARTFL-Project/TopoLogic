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
                <b-card
                    no-body
                    class="shadow-sm"
                    :header="`Word distribution of ${word} across topics`"
                >
                    <div class="p-2">
                        <apexchart
                            type="bar"
                            width="100%"
                            height="400px"
                            :options="options"
                            :series="series"
                        ></apexchart>
                    </div>
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
                            >{{doc.score.toFixed(3)}}</b-badge>
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
            options: {
                chart: {
                    id: "topic-distribution",
                    toolbar: {
                        show: false
                    },
                    events: {
                        click: this.goToTopic
                    }
                },
                xaxis: {
                    categories: []
                },
                yaxis: {
                    labels: {
                        formatter: val => val.toFixed(2)
                    }
                },
                grid: {
                    padding: {
                        left: 0,
                        right: 0,
                        top: 0,
                        bottom: 0
                    }
                },
                dataLabels: {
                    enabled: false
                },
                tooltip: {
                    x: {
                        formatter: val =>
                            `Topic ${val}: ${topicData[val].description}`
                    },
                    y: {
                        formatter: val => val.toFixed(4)
                    }
                }
            },
            series: [
                {
                    name: "",
                    data: []
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
                    `${this.$globalConfig.apiServer}/get_word_data/${this.$route.params.word}?table=${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.word = response.data.word;
                    this.documents = response.data.documents;
                    this.build_topic_distribution(
                        response.data.topic_distribution
                    );
                })
                .catch(error => {
                    this.word = this.$route.params.word;
                    this.notFound = true;
                });
        },
        build_topic_distribution(topicDistribution) {
            this.series[0].data = topicDistribution.data;
            this.options = {
                ...this.options,
                ...{
                    xaxis: {
                        categories: topicDistribution.labels
                    }
                }
            };
        },
        loadNewData() {
            this.fetchData();
        },
        goToTopic() {
            let seriesIndex = parseInt(event.target.getAttribute("j"));
            this.$router.push(
                `/topic/${this.options.xaxis.categories[seriesIndex]}`
            );
        }
    }
};
</script>