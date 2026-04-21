<template>
    <div class="container-fluid mt-4">
        <div class="card shadow-sm mb-4">
            <div class="card-header">
                <h6 class="mb-0 text-center">
                    Topics and their relative distribution in
                    <b>{{ fieldValue }}</b>
                </h6>
            </div>
            <sortable-table
                :items="sortedTopicDistribution"
                :fields="fields"
                :initial-sort-by="initialSortBy"
                :initial-sort-desc="initialSortDesc"
                @row-clicked="goToTopic"
            >
                <template v-slot:cell(name)="data">
                    <span class="frequency-parent">Topic {{ data.value }}</span>
                </template>
                <template v-slot:cell(description)="data">
                    <span class="frequency-parent">{{ data.value }}</span>
                </template>
                <template v-slot:cell(frequency)="data">
                    <span class="frequency-value ps-2">{{ data.value }}%</span>
                    <span class="frequency-bar" :style="`width: ${data.value / 100 * frequencyMultiplier}%;`"></span>
                </template>
            </sortable-table>
        </div>
    </div>
</template>

<script>
import topicData from "../../topic_words.json";
import SortableTable from "./SortableTable.vue";

export default {
    name: "topicDistributions",
    components: { SortableTable },
    props: ["topics"],
    data() {
        return {
            routeName: this.$route.name,
            localTopics: this.topics || topicData
        };
    },
    mounted() {
        document
            .querySelectorAll("tr > td:nth-child(3)")
            .forEach(function (element) {
                element.style.position = "relative";
                element.style.padding = "0.75rem";
            });
    },
    computed: {
        fields: function () {
            let fields = [
                { key: "name", label: "Topic", sortable: true },
                { key: "description", label: "Top 10 tokens", sortable: false },
                {
                    key: "frequency",
                    label: "Relative global weight across corpus",
                    sortable: true
                }
            ];
            if (this.routeName != "home") {
                fields[2].label = `Proportion in ${this.$route.params.fieldName}`;
            }
            return fields;
        },
        initialSortBy() {
            return this.$route.name === "home" ? "name" : "frequency";
        },
        initialSortDesc() {
            return this.$route.name !== "home";
        },
        frequencyMultiplier() {
            let maxFrequency = 0.0;
            for (let topic of this.localTopics) {
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
            for (let topicName in this.localTopics) {
                topicsWithDescription.push({
                    name: `${topicName}`,
                    description: topicData[topicName].label || topicData[topicName].description,
                    frequency: this.smartRound(this.localTopics[topicName].frequency * 100)
                });
            }
            return topicsWithDescription;
        }
    },
    methods: {
        goToTopic(topic) {
            if (this.routeName == "home") {
                this.$router.push(`/topic/${topic.name}`);
            } else {
                if (topic.name.length.toString() == 1) {
                    window.open(
                        `${this.$globalConfig.philoLogicUrl}/query?report=bibliography&${this.$route.params.fieldName}="${this.$route.params.fieldValue}"&alltopicmodels=0${topic.name}`,
                        "_blank"
                    );
                } else {
                    window.open(
                        `${this.$globalConfig.philoLogicUrl}/query?report=bibliography&${this.$route.params.fieldName}="${this.$route.params.fieldValue}"&alltopicmodels=${topic.name}`,
                        "_blank"
                    );
                }
            }
        },
        smartRound(num) {
            num = parseFloat(num);
            return num === 0 ? "0.00" : Number(num.toPrecision(2)).toString();
        }
    }
};
</script>

<style scoped lang="scss">
@use "../assets/styles/theme.module.scss" as theme;

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
    background-color: rgba(theme.$link-color, 0.3);
    background-clip: content-box;
}

:deep(td) {
    cursor: pointer;
}
</style>
