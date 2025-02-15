<template>
    <b-container fluid class="mt-4">
        <b-card no-body class="shadow-sm mb-4">
            <h6 slot="header" class="mb-0 text-center">
                Topics and their relative distribution in
                <b>{{ fieldValue }}</b>
            </h6>
            <b-table hover :items="sortedTopicDistribution" :fields="fields" :sort-by.sync="sortBy"
                :sort-desc.sync="sortDesc" @row-clicked="goToTopic">
                <template v-slot:cell(name)="data">
                    <span class="frequency-parent">Topic {{ data.value }}</span>
                </template>
                <template v-slot:cell(description)="data">
                    <span class="frequency-parent">{{ data.value }}</span>
                </template>
                <template v-slot:cell(frequency)="data">
                    <span class="frequency-value pl-2">{{ data.value }}%</span>
                    <span class="frequency-bar" :style="`width: ${data.value / 100 * frequencyMultiplier}%;`"></span>
                </template>
            </b-table>
        </b-card>
    </b-container>
</template>

<script>
import topicData from "../../topic_words.json";

export default {
    name: "topicDistributions",
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
        sortBy: {
            get: function () {
                if (this.$route.name == "home") {
                    return "name";
                } else {
                    return "frequency";
                }
            },
            set: value => {
                return value;
            }
        },
        sortDesc: {
            get: function () {
                if (this.$route.name == "home") {
                    return false;
                } else {
                    return true;
                }
            },
            set: value => {
                return value;
            }
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
                    description: topicData[topicName].description,
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
            if (num === 0) return "0.00";

            // Convert to string and find first non-zero digit after decimal
            const str = num.toFixed(20);
            const decimal = str.split('.')[1];
            let leadingZeros = '';
            let firstNonZeroIndex = 0;

            // Count leading zeros
            for (let i = 0; i < decimal.length; i++) {
                if (decimal[i] === '0') {
                    leadingZeros += '0';
                } else {
                    firstNonZeroIndex = i;
                    break;
                }
            }

            // Get the significant part (two digits after first non-zero)
            const significantPart = decimal.slice(firstNonZeroIndex, firstNonZeroIndex + 2);
            const restOfNumber = decimal.slice(firstNonZeroIndex + 2);

            // Round if there are more digits
            let roundedSignificant = significantPart;
            if (restOfNumber.length > 0) {
                const roundingDigit = parseInt(restOfNumber[0]);
                let num = parseInt(significantPart);
                if (roundingDigit >= 5) {
                    num++;
                    roundedSignificant = num.toString().padStart(2, '0');
                }
            }

            return `0.${leadingZeros}${roundedSignificant}`;
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

/deep/ td {
    cursor: pointer;
}
</style>
