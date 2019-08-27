<template>
    <b-container fluid class="mt-4">
        <b-card no-body class="shadow-sm p-2 mb-4">
            <h5 class="card-title pt-2" style="text-align: center;">
                Topics and their relative distribution
                <b>{{ fieldValue }}</b>
                <div style="font-size: 70%">Click to get detailed distribution</div>
            </h5>
            <b-row
                v-for="topic in sortedTopicDistribution"
                :key="topic.name"
                class="mb-1 mr-1"
                style="padding: .1rem; cursor: pointer"
                @click="goToTopic(topic.name)"
            >
                <b-col cols="2" style="text-align: right">
                    <b>Topic {{topic.name}}</b>
                    ({{(topic.frequency*100).toFixed(2)}}%):
                </b-col>
                <b-col cols="8" class="position-relative pl-2">
                    {{topic.description}}
                    <span
                        class="position-absolute"
                        :style="`display: inline-block; background-color: rgba(85,172,238, .4); height: 100%; left: 0; top: 0; width: ${topic.frequency*frequencyMultiplier}%;`"
                    ></span>
                </b-col>
            </b-row>
        </b-card>
    </b-container>
</template>

<script>
import Chart from "chart.js/dist/Chart.js";
import topicData from "../../topic_words.json";

export default {
    name: "topicDistributions",
    props: ["topics"],
    data() {
        return {
            routeName: this.$route.name
        };
    },
    computed: {
        frequencyMultiplier: function() {
            let maxFrequency = 0.0;
            for (let topic of this.topics) {
                if (topic.frequency > maxFrequency) {
                    maxFrequency = topic.frequency;
                }
            }
            return 100 / maxFrequency;
        },
        fieldValue() {
            if (this.$route.name == "home") {
                return "across the corpus";
            } else {
                return `in ${this.$route.params.fieldValue}`;
            }
        },
        sortedTopicDistribution() {
            let topicsWithDescription = [];
            for (let topicName in this.topics) {
                topicsWithDescription.push({
                    name: topicName,
                    description: topicData[topicName].description,
                    frequency: this.topics[topicName].frequency
                });
            }
            topicsWithDescription.sort(function(a, b) {
                return b.frequency - a.frequency;
            });
            return topicsWithDescription;
        }
    },
    methods: {
        goToTopic(topic) {
            this.$router.push(`/topic/${topic}`);
        }
    }
};
</script>

<style scoped>
</style>
