<template>
    <div class="container-fluid my-4">
        <div class="card shadow-sm">
            <div class="card-header">Corpus overview</div>
            <div class="row pt-3 px-3" v-if="loaded">
                <div class="col-8" v-if="hasYearHistogram">
                    <h6 class="mb-3 text-center">Documents per year</h6>
                    <v-chart :option="yearChartOption" :autoresize="false" style="height: 340px; width: 100%"></v-chart>
                </div>
                <div :class="hasYearHistogram ? 'col-4' : 'col-12'">
                    <div v-for="field in fieldsWithData" :key="field" class="mb-3">
                        <h6 class="mb-2 text-capitalize">Top {{ field }}s</h6>
                        <ul class="list-group list-group-flush">
                            <li v-for="entry in overview.field_distributions[field]" :key="entry.value"
                                class="list-group-item d-flex justify-content-between align-items-center py-1"
                                style="font-size: 0.9rem">
                                <router-link
                                    class="text-truncate me-2"
                                    :to="`/metadata/${encodeURIComponent(field)}/${encodeURIComponent(entry.value)}`"
                                    :title="entry.value"
                                >{{ entry.value }}</router-link>
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
        yearChartOption() {
            const years = this.overview.year_distribution.map((e) => e.year);
            const counts = this.overview.year_distribution.map((e) => e.count);
            // Cap to ~10 labels on the x-axis, mirroring the prior tickAmount: 10 setting.
            const labelInterval = Math.max(0, Math.ceil(years.length / 10) - 1);
            return {
                // Animations are the main cost for a 100+ bar histogram — turning
                // them off cuts render time by >5x with no loss of information.
                animation: false,
                grid: { left: 45, right: 10, top: 10, bottom: 30, containLabel: true },
                xAxis: {
                    type: "category",
                    data: years,
                    axisLabel: { hideOverlap: true, interval: labelInterval },
                },
                yAxis: {
                    type: "value",
                    axisLabel: {
                        formatter: (val) => (typeof val === "number" ? String(Math.round(val)) : val),
                    },
                },
                tooltip: {
                    trigger: "axis",
                    axisPointer: { type: "shadow" },
                    formatter: (params) => `${params[0].name}<br/>${params[0].value} docs`,
                },
                series: [
                    {
                        name: "Documents",
                        type: "bar",
                        data: counts,
                        barWidth: "90%",
                        itemStyle: { color: "#ad4242", opacity: 0.9 },
                        emphasis: { disabled: true },
                    },
                ],
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
