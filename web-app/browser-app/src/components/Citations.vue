<template>
    <div class="d-inline-block">
        <span
            v-for="(citation, citeIndex) in citations"
            :key="citation.field"
            :style="citation.style"
        >
            <router-link v-if="citation.link && doc.doc_id != ''" :to="docLink()">
                {{
                doc.metadata[citation.field] || "Unnamed section"
                }}
            </router-link>
            <span v-else>{{ doc.metadata[citation.field] }}</span>
            <span class="separator" v-if="citeIndex != citations.length - 1">&#9679;</span>
        </span>

        <br />
        <router-link :to="readingLink()" v-if="doc.philo_type">Navigate to full text</router-link>
    </div>
</template>
<script>
export default {
    name: "Citations",
    props: ["doc", "philoDb"],
    data() {
        return {
            citations: this.$globalConfig.citations[this.philoDb],
        };
    },
    methods: {
        docLink() {
            let philoType = `philo_${this.doc.metadata.philo_type}_id`;
            let url = `/document/${this.philoDb}/${this.doc.metadata[philoType]
                .split(" ")
                .join("/")}`;
            return url;
        },
        readingLink() {
            let philoType = `philo_${this.doc.metadata.philo_type}_id`;
            let objectId = this.doc.metadata[philoType].split(" ").join("/");
            return `/reading/${this.philoDb}/${objectId}`;
        },
    }
};
</script>
<style scoped lang="scss">
@use "../assets/styles/theme.module.scss" as theme;

.separator {
    display: inline-block;
    margin: 0 0.25rem;
    font-style: italic;
}
a:not([href]) {
    color: theme.$link-color;
    cursor: pointer;
}
a:not([href]):hover {
    color: theme.$link-color;
}
</style>
