<template>
    <div class="container-fluid">
        <div class="d-flex justify-content-center" style="margin-top: 200px" v-if="loading">
            <div class="spinner-border" style="width: 10rem; height: 10rem;" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
        <h5 class="text-center mt-4 mb-4" v-if="!loading">{{ header }}</h5>
        <div class="row">
            <div class="col-6" v-for="(halfGroup, halfIndex) in fieldValues" :key="halfIndex">
                <div
                    class="card mb-4 shadow-sm"
                    v-for="(group, index) in halfGroup"
                    :key="index"
                >
                    <div class="card-header">{{ group.firstLetter }}</div>
                    <ul class="list-group list-group-flush">
                        <li
                            class="list-group-item"
                            style="padding: .5rem 1rem"
                            v-for="(value, valueIndex) in group.fields"
                            :key="valueIndex"
                        >
                            <router-link
                                :to="`/${fieldName}/${value}`"
                                v-if="fieldName == 'word'"
                            >{{ value }}</router-link>
                            <router-link
                                :to="`/metadata/${fieldName}/${value}`"
                                v-if="fieldName != 'word'"
                            >{{ value }}</router-link>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
export default {
    name: "FieldView",
    data() {
        return {
            fieldName: this.$route.params.fieldName,
            fieldValues: [],
            totalFields: 0,
            loading: false
        };
    },
    computed: {
        header: function() {
            if (this.fieldName == "word") {
                return `${this.totalFields} distinct tokens across the corpus`;
            } else {
                if (this.$route.query.filter == 1) {
                    return `${this.totalFields} ${this.fieldName}s across the corpus`;
                }
                return `${this.totalFields} ${this.fieldName}s (with at least ${this.$route.query.filter} instances) across the corpus`;
            }
        }
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
            this.fieldName = this.$route.params.fieldName;
            this.fieldValues = [];
            this.totalFields = 0;
            this.loading = true;
            let UrlString;
            if (typeof this.$route.query.filter == "undefined") {
                UrlString = `${this.$globalConfig.apiServer}/get_all_field_values/${this.$globalConfig.databaseName}?field=${this.$route.params.fieldName}`;
            } else {
                UrlString = `${this.$globalConfig.apiServer}/get_all_field_values/${this.$globalConfig.databaseName}?field=${this.$route.params.fieldName}&filter=${this.$route.query.filter}`;
            }
            this.$http.get(UrlString).then(response => {
                this.totalFields = response.data.field_values.length;
                this.fieldValues = this.splitResults(
                    response.data.field_values
                );
                this.$nextTick(() => {
                    this.loading = false;
                });
            });
        },
        splitResults(fieldValues) {
            let firstLetter = fieldValues[0][0].toUpperCase();
            let currentGroup = [];
            let sortedFields = [];
            for (let field of fieldValues) {
                let currentFirstLetter = field[0].toUpperCase();
                if (currentFirstLetter === firstLetter) {
                    currentGroup.push(field);
                } else {
                    sortedFields.push({
                        firstLetter: firstLetter,
                        fields: Object.freeze(currentGroup)
                    });
                    firstLetter = currentFirstLetter;
                    currentGroup = [field];
                }
            }
            sortedFields.push({
                firstLetter: firstLetter,
                fields: Object.freeze(currentGroup)
            });
            let half = Math.floor(sortedFields.length / 2);

            return Object.freeze([
                sortedFields.slice(0, half),
                sortedFields.slice(half, sortedFields.length)
            ]);
        }
    }
};
</script>

