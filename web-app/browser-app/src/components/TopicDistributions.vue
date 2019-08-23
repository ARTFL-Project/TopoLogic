<template>
    <b-container fluid class="mt-4">
        <b-card no-body class="shadow-sm p-2 mb-4">
            <h5 class="card-title pt-2" style="text-align: center;">
                Topics and their relative distribution across the corpus
                <div style="font-size: 70%">Click to get detailed distribution</div>
            </h5>
            <b-row
                v-for="topic in topicData"
                :key="topic.name"
                class="mb-1 mr-1"
                style="padding: .1rem; cursor: pointer"
                @click="goToTopic(topic.name)"
            >
                <b-col cols="2" style="text-align: right">
                    <b>Topic {{topic.name}}</b>
                    ({{(topic.frequency*100).toFixed(2)}}%):
                </b-col>
                <b-col cols="10" class="position-relative pl-2">
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
import topics from "../../topic_words.json";
import Chart from "chart.js/dist/Chart.js";

export default {
    name: "TopicDistributions",
    data() {
        return {
            topicData: topics
        };
    },
    computed: {
        frequencyMultiplier: function() {
            let maxFrequency = 0.0;
            for (let topic of topics) {
                if (topic.frequency > maxFrequency) {
                    maxFrequency = topic.frequency;
                }
            }
            return 100 / maxFrequency;
        }
    },
    methods: {
        goToTopic(topic) {
            this.$router.push(`/topic/${topic}`);
        }
    }
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
