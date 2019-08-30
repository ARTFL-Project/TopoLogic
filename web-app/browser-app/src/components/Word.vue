<template>
    <b-container fluid class="mt-4">
        <h5 class="text-center">
            Distribution of
            <b>{{ word }}</b> in the corpus
        </h5>
        <div class="row mt-4 p-2">
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
                            <router-link :to="`/document/${doc.doc_id}`">
                                <i>{{ doc.metadata.title }}</i>
                            </router-link>
                            &#9702;&nbsp;{{ doc.metadata.author }}
                            <b-badge
                                variant="primary"
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

export default {
    name: "Word",
    data() {
        return {
            word: "",
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
        }
    }
};
</script>