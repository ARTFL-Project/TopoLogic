<template>
    <ul class="nav nav-tabs doc-tabs mb-3">
        <li class="nav-item">
            <router-link class="nav-link" :class="{ active: $route.name === 'document' }"
                :to="{ name: 'document', params: { philoDb, doc } }">
                Summary
            </router-link>
        </li>
        <li class="nav-item">
            <router-link class="nav-link" :class="{ active: $route.name === 'topicalReading' }"
                :to="{ name: 'topicalReading', params: { philoDb, doc } }">
                Topical reading
            </router-link>
        </li>
    </ul>
</template>

<script>
export default {
    name: "DocTabs",
    computed: {
        philoDb() {
            return this.$route.params.philoDb;
        },
        doc() {
            return this.$route.params.doc;
        },
    },
};
</script>

<style scoped>
.doc-tabs {
    font-size: 0.95rem;
}
</style>
