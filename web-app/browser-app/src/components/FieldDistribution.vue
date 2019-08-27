<template>
    <b-container fluid class="mt-4">
        <topic-distributions></topic-distributions>
    </b-container>
</template>
<script>
import topicDistributions from "./TopicDistributions";

export default {
    name: "FieldDistribution",
    components: {
        topicDistributions
    },
    data() {
        return {
            fieldName: this.$route.params.fieldName,
            fieldValue: this.$route.params.fieldValue
        };
    }
};
</script>