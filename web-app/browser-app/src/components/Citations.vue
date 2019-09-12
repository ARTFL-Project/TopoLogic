<template>
    <div class="d-inline-block">
        <span
            v-for="(citation, citeIndex) in citations"
            :key="citation.field"
            :style="citation.style"
        >
            <router-link
                :to="`/document/${doc.doc_id}`"
                v-if="citation.field == 'title' && doc.doc_id != ''"
            >{{ doc.metadata.title }}</router-link>
            <span v-else>{{ doc.metadata[citation.field] }}</span>
            <span class="separator" v-if="citeIndex != citations.length - 1">&#9679;</span>
        </span>
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