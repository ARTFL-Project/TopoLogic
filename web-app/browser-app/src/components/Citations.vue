<template>
    <div class="d-inline-block">
        <span
            v-for="(citation, citeIndex) in citations"
            :key="citation.field"
            :style="citation.style"
        >
            <router-link :to="`/document/${philoId}`" v-if="citation.link && doc.doc_id != ''">
                {{
                doc.metadata[citation.field] || "Unnamed section"
                }}
            </router-link>
            <span v-else>{{ doc.metadata[citation.field] }}</span>
            <span class="separator" v-if="citeIndex != citations.length - 1">&#9679;</span>
        </span>
        <br />
        <a :href="goToPhilo()" target="_blank" v-if="doc.philo_type">Navigate to full text</a>
    </div>
</template>
<script>
export default {
    name: "Citations",
    props: ["doc"],
    data() {
        return {
            citations: this.$globalConfig.metadataFields
        };
    },
    computed: {
        philoId() {
            return this.doc.metadata.philo_id
                .split(" ")
                .filter(id => id != "0")
                .join(" ");
        }
    },
    methods: {
        goToPhilo() {
            let trimmedId = this.doc.philo_id.split(" ").filter(id => {
                return parseInt(id) > 0;
            });
            if (this.doc.philo_type == "doc") {
                return `${this.$globalConfig.philoLogicUrl}/navigate/${trimmedId}/table-of-contents`;
            }
            return `${this.$globalConfig.philoLogicUrl}/navigate/${trimmedId}`;
        }
    }
};
</script>
<style scoped>
.separator {
    display: inline-block;
    margin: 0 0.25rem;
    font-style: italic;
}
</style>
