<template>
    <div class="container-fluid mt-4">
        <topic-distributions v-if="topics.length" :topics="topics"></topic-distributions>
    </div>
</template>
<script>
import topicDistributions from "./TopicDistributions.vue";

export default {
    name: "FieldDistribution",
    components: {
        topicDistributions
    },
    data() {
        return {
            fieldName: this.$route.params.fieldName,
            fieldValue: this.$route.params.fieldValue,
            topics: []
        };
    },
    created() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "fetchData"
    },
    methods: {
        fetchData() {
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_field_distribution/${this.$globalConfig.databaseName}/${this.$route.params.fieldName}?value=${this.$route.params.fieldValue}`
                )
                .then(response => {
                    this.topics = response.data.topic_distribution;
                });
        }
    }
};
</script>