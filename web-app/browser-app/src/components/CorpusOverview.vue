<template>
    <div class="container-fluid my-4">
        <div class="card shadow-sm">
            <div class="card-header">Corpus overview</div>
            <div class="row pt-3 px-3" v-if="loaded">
                <div class="col-8" v-if="hasYearHistogram">
                    <h6 class="mb-3 text-center">Documents per year</h6>
                    <apexchart type="bar" height="340" :options="yearChartOptions" :series="yearSeries"></apexchart>
                </div>
                <div :class="hasYearHistogram ? 'col-4' : 'col-12'">
                    <div v-for="field in fieldsWithData" :key="field" class="mb-3">
                        <h6 class="mb-2 text-capitalize">Top {{ field }}s</h6>
                        <ul class="list-group list-group-flush">
                            <li v-for="entry in overview.field_distributions[field]" :key="entry.value"
                                class="list-group-item d-flex justify-content-between align-items-center py-1"
                                style="font-size: 0.9rem">
                                <span class="text-truncate me-2" :title="entry.value">{{ entry.value }}</span>
                                <span class="badge rounded-pill bg-secondary">{{ entry.count }}</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="p-3 text-muted" v-else>Loading…</div>
        </div>
    </div>
</template>

<script>
export default {
    name: "CorpusOverview",
    data() {
        return {
            loaded: false,
            overview: { year_distribution: [], field_distributions: {} },
        };
    },
    computed: {
        hasYearHistogram() {
            return this.overview.year_distribution && this.overview.year_distribution.length > 0;
        },
        fieldsWithData() {
            return Object.keys(this.overview.field_distributions || {}).filter(
                (f) => this.overview.field_distributions[f] && this.overview.field_distributions[f].length > 0
            );
        },
        yearSeries() {
            return [
                {
                    name: "Documents",
                    data: this.overview.year_distribution.map((e) => e.count),
                },
            ];
        },
        yearChartOptions() {
            return {
                chart: {
                    id: "corpus-year-histogram",
                    toolbar: { show: false },
                    // Animations are the main cost for a 100+ bar histogram — turning
                    // them off cuts render time by >5x with no loss of information.
                    animations: { enabled: false },
                    redrawOnParentResize: false,
                    redrawOnWindowResize: false,
                },
                dataLabels: { enabled: false },
                states: {
                    hover: { filter: { type: "none" } },
                    active: { filter: { type: "none" } },
                },
                xaxis: {
                    categories: this.overview.year_distribution.map((e) => e.year),
                    tickAmount: 10,
                    labels: { hideOverlappingLabels: true },
                },
                yaxis: {
                    labels: {
                        formatter: (val) => (typeof val === "number" ? String(Math.round(val)) : val),
                    },
                },
                fill: { opacity: 0.9 },
                colors: ["#ad4242"],
                grid: { padding: { left: 0, right: 0, top: 0, bottom: 0 } },
                plotOptions: { bar: { columnWidth: "90%" } },
                tooltip: {
                    y: { formatter: (val) => `${val} docs` },
                },
            };
        },
    },
    created() {
        // Ask for top distributions on each configured metadata-distribution field.
        const fields = (this.$globalConfig.metadataDistributions || [])
            .map((m) => m.field)
            .join(",");
        this.$http
            .get(
                `${this.$globalConfig.apiServer}/get_corpus_overview/${this.$globalConfig.databaseName}`,
                { params: { fields } }
            )
            .then((response) => {
                this.overview = response.data;
                this.loaded = true;
            })
            .catch(() => {
                this.loaded = true;  // show nothing rather than a spinner forever
            });
    },
};
</script>
