<template>
    <div class="container-fluid mt-3">
        <div class="d-flex align-items-baseline flex-wrap gap-3 mb-3" v-if="selectedField">
            <h5 class="mb-0">
                <span class="text-muted">Browsing</span>
                <b class="ms-2">{{ fieldLabel(selectedField) }}</b>
            </h5>
            <span class="text-muted small" v-if="totalFields > 0">
                {{ totalFields }} {{ fieldLabelPlural(selectedField) }}
                <span v-if="isNavMode" class="ms-1">· click to open the document</span>
            </span>
        </div>

        <div class="d-flex justify-content-center" style="margin-top: 200px" v-if="loading">
            <div class="spinner-border" style="width: 6rem; height: 6rem" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>

        <div
            v-else-if="!selectedField"
            class="text-center text-muted mt-5"
        >
            Pick a metadata field from the
            <b>Metadata Explorer</b> menu above to start browsing.
        </div>

        <div v-else class="row">
            <div
                class="col-6"
                v-for="(halfGroup, halfIndex) in fieldValues"
                :key="halfIndex"
            >
                <div
                    class="card mb-4 shadow-sm"
                    v-for="(group, index) in halfGroup"
                    :key="index"
                >
                    <div class="card-header">{{ group.firstLetter }}</div>
                    <ul class="list-group list-group-flush">
                        <li
                            class="list-group-item"
                            style="padding: 0.5rem 1rem"
                            v-for="(entry, valueIndex) in group.fields"
                            :key="valueIndex"
                        >
                            <router-link :to="entry.linkTo">{{ entry.label }}</router-link>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
const FIELD_LABELS = {
    author: "Author",
    text_genre: "Genre",
    publisher: "Publisher",
    pub_place: "Place of publication",
    collection: "Collection",
    editor: "Editor",
    keywords: "Keywords",
    pub_date: "Publication date",
    create_date: "Creation date",
    title: "Title",
    notes: "Notes",
    text_form: "Form",
    auth_gender: "Author gender",
};

const FIELD_LABELS_PLURAL = {
    author: "authors",
    text_genre: "genres",
    publisher: "publishers",
    pub_place: "places",
    collection: "collections",
    editor: "editors",
    keywords: "keyword sets",
    pub_date: "dates",
    create_date: "dates",
    title: "titles",
    notes: "notes",
    text_form: "forms",
    auth_gender: "author genders",
};

export default {
    name: "MetadataExplorer",
    data() {
        return {
            loading: true,
            profiledFields: [],
            fieldValues: [],
            totalFields: 0,
        };
    },
    computed: {
        selectedField() {
            return this.$route.params.field || "";
        },
        selectedFieldInfo() {
            return this.profiledFields.find((f) => f.field === this.selectedField);
        },
        isNavMode() {
            return this.selectedFieldInfo && this.selectedFieldInfo.kind === "navigate";
        },
    },
    created() {
        this.fetchProfiledFields();
    },
    watch: {
        $route() {
            if (this.selectedField) this.fetchValues(this.selectedField);
        },
    },
    methods: {
        fieldLabel(field) {
            return FIELD_LABELS[field] || field;
        },
        fieldLabelPlural(field) {
            return FIELD_LABELS_PLURAL[field] || `${field}s`;
        },
        fetchProfiledFields() {
            this.loading = true;
            this.$http
                .get(`${this.$globalConfig.apiServer}/get_profiled_fields/${this.$globalConfig.databaseName}`)
                .then((response) => {
                    this.profiledFields = response.data.fields || [];
                    const chosen = this.selectedField;
                    if (chosen) {
                        this.fetchValues(chosen);
                    } else {
                        this.loading = false;
                    }
                })
                .catch(() => {
                    this.profiledFields = [];
                    this.loading = false;
                });
        },
        fetchValues(field) {
            this.loading = true;
            this.fieldValues = [];
            this.totalFields = 0;
            const info = this.profiledFields.find((f) => f.field === field);
            const isNav = info && info.kind === "navigate";
            const request = isNav ? this.fetchNavValues(field) : this.fetchProfileValues(field);
            request.finally(() => {
                this.loading = false;
            });
        },
        fetchProfileValues(field) {
            // Filter matches the ≥ 2 docs threshold used for the profile pass;
            // keeps the grid in sync with what actually has a profile.
            return this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_all_field_values/${this.$globalConfig.databaseName}` +
                    `?field=${encodeURIComponent(field)}&filter=2`
                )
                .then((response) => {
                    const values = response.data.field_values || [];
                    this.totalFields = values.length;
                    const entries = values.map((v) => ({
                        sortKey: v,
                        label: v,
                        linkTo: `/metadata/${field}/${encodeURIComponent(v)}`,
                    }));
                    this.fieldValues = this.splitResults(entries);
                });
        },
        fetchNavValues(field) {
            return this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_field_navigation_values/${this.$globalConfig.databaseName}` +
                    `?field=${encodeURIComponent(field)}`
                )
                .then((response) => {
                    const values = response.data.values || [];
                    this.totalFields = values.length;
                    const entries = values.map((v) => ({
                        sortKey: v.value,
                        label: v.value,
                        linkTo: this.docLink(v),
                    }));
                    this.fieldValues = this.splitResults(entries);
                });
        },
        docLink(v) {
            // Document.vue expects the philo_id path split on spaces → slashes,
            // with object depth determined by object_level (doc, div1, ...).
            const id = (v.philo_id || "").split(" ").join("/");
            return `/document/${v.philo_db}/${id}`;
        },
        splitResults(entries) {
            if (!entries.length) return [];
            const firstChar = (s) => (s || "?").charAt(0).toUpperCase();
            let firstLetter = firstChar(entries[0].sortKey);
            let currentGroup = [];
            const sortedFields = [];
            for (const entry of entries) {
                const currentFirstLetter = firstChar(entry.sortKey);
                if (currentFirstLetter === firstLetter) {
                    currentGroup.push(entry);
                } else {
                    sortedFields.push({
                        firstLetter,
                        fields: Object.freeze(currentGroup),
                    });
                    firstLetter = currentFirstLetter;
                    currentGroup = [entry];
                }
            }
            sortedFields.push({
                firstLetter,
                fields: Object.freeze(currentGroup),
            });
            const half = Math.ceil(sortedFields.length / 2);
            return Object.freeze([
                sortedFields.slice(0, half),
                sortedFields.slice(half),
            ]);
        },
    },
};
</script>
