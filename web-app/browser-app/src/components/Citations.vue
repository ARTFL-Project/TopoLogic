<template>
    <div class="d-inline-block">
        <span
            v-for="(citation, citeIndex) in citations"
            :key="citation.field"
            :style="citation.style"
        >
            <a :id="`${target}`" v-if="citation.link && doc.doc_id != ''">
                {{
                doc.metadata[citation.field] || "Unnamed section"
                }}
            </a>
            <span v-else>{{ doc.metadata[citation.field] }}</span>
            <span class="separator" v-if="citeIndex != citations.length - 1">&#9679;</span>
        </span>
        <doc-link :target="`${target}`" :metadata="doc.metadata"></doc-link>

        <br />
        <a :href="goToPhilo()" target="_blank" v-if="doc.philo_type">Navigate to full text</a>
    </div>
</template>
<script>
import DocLink from "./DocLink";

export default {
    name: "Citations",
    components: { DocLink },
    props: ["doc", "target"],
    data() {
        return {
            citations: this.$globalConfig.metadataFields,
            philoUrl: this.$globalConfig.philoLogicUrl
        };
    },
    methods: {
        goToPhilo() {
            let philoType = `philo_${this.doc.metadata.philo_type}_id`;
            if (this.doc.metadata.philo_type == "doc") {
                return `${this.philoUrl}/navigate/${this.doc.metadata[philoType]}/table-of-contents/`;
            } else {
                let objectId = this.doc.metadata[philoType]
                    .split(" ")
                    .join("/");
                return `${this.philoUrl}/navigate/${objectId}/`;
            }
            // let trimmedId = this.doc.metadata[
            //     `philo_${this.doc.metadata.philo_type}_id`
            // ]
            //     .split(" ")
            //     .join("/");

            // if (this.doc.philo_type == "doc") {
            //     return `${this.$globalConfig.philoLogicUrl}/navigate/${this.trimmedId}/table-of-contents`;
            // }
            // return `${this.$globalConfig.philoLogicUrl}/navigate/${trimmedId}`;
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
a:not([href]) {
    color: #55acee;
    cursor: pointer;
}
a:not([href]):hover {
    color: #55acee;
    text-decoration: underline;
}
</style>
