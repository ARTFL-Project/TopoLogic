<template>
    <b-container fluid class="mt-4">
        <b-card no-body class="shadow-sm mb-4">
            <h6 slot="header" class="mb-0 text-center">
                Topics and their relative distribution in
                <b>{{fieldValue}}</b>
            </h6>
            <b-table
                hover
                :items="sortedTopicDistribution"
                :fields="fields"
                :sort-by.sync="sortBy"
                :sort-desc.sync="sortDesc"
                @row-clicked="goToTopic"
            >
                <template slot="[name]" slot-scope="data">
                    <span class="frequency-parent">Topic {{ data.value }}</span>
                </template>
                <template slot="[description]" slot-scope="data">
                    <span class="frequency-parent">{{ data.value }}</span>
                </template>
                <template slot="[frequency]" slot-scope="data">
                    <span
                        class="frequency-value pl-2"
                    >{{ (data.value.toFixed(3) * 100).toFixed(1) }}%</span>
                    <span
                        class="frequency-bar"
                        :style="`width: ${data.value*frequencyMultiplier}%;`"
                    ></span>
                </template>
            </b-table>
            <!-- <b-row
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
            </b-row>-->
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
    mounted() {
        var vm = this;
        document
            .querySelectorAll("tr > td:nth-child(3)")
            .forEach(function(element, index) {
                element.style.position = "relative";
                element.style.padding = "0.75rem";
            });
    },
    computed: {
        fields: function() {
            let fields = [
                { key: "name", label: "Topic", sortable: true },
                { key: "description", label: "Top 10 tokens", sortable: false },
                {
                    key: "frequency",
                    label: "Proportion across corpus",
                    sortable: true
                }
            ];
            if (this.routeName != "home") {
                fields[2].label = `Proportion in ${this.$route.params.fieldName}`;
            }
            return fields;
        },
        sortBy: function() {
            if (this.$route.name == "home") {
                return "name";
            } else {
                return "frequency";
            }
        },
        sortDesc: function() {
            if (this.$route.name == "home") {
                return false;
            } else {
                return true;
            }
        },
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
                return "the corpus";
            } else {
                return `${this.$route.params.fieldValue}`;
            }
        },
        sortedTopicDistribution() {
            let topicsWithDescription = [];
            for (let topicName in this.topics) {
                topicsWithDescription.push({
                    name: `${topicName}`,
                    description: topicData[topicName].description,
                    frequency: this.topics[topicName].frequency
                });
            }
            return topicsWithDescription;
        }
    },
    methods: {
        goToTopic(topic) {
            this.$router.push(`/topic/${topic.name}`);
        }
    }
};
</script>

<style scoped>
.frequency-value {
    display: inline-block;
}
.frequency-bar {
    display: inline-block;
    position: absolute;
    left: 0;
    top: 0;
    padding: 0.75rem;
    height: 100%;
    background-color: rgba(85, 172, 238, 0.4);
    background-clip: content-box;
}
</style>
