<template>
    <div class="container-fluid mt-3">
        <div v-if="loading" class="d-flex justify-content-center" style="margin-top: 200px">
            <div class="spinner-border" style="width: 5rem; height: 5rem" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>

        <template v-else-if="profile">
            <div class="profile-header mb-3">
                <div class="d-flex align-items-baseline flex-wrap gap-3">
                    <h5 class="mb-0">
                        <span class="text-secondary text-capitalize">{{ fieldLabel }}:</span>
                        <b class="ms-2">{{ profile.field_value }}</b>
                    </h5>
                    <span class="badge bg-secondary">{{ profile.doc_count }} documents</span>
                    <span
                        class="badge focus-badge"
                        :title="focusTooltip"
                    >{{ focusLabel }}</span>
                    <span class="text-muted small" v-if="trajectoryYearRange">
                        {{ trajectoryYearRange }}
                    </span>
                </div>
            </div>

            <div class="row g-3">
                <div class="col-lg-8">
                    <div class="card shadow-sm">
                        <div class="card-header">
                            Distinctive topics
                            <span class="text-muted small ms-2">
                                (topic weight ÷ corpus average; higher = more characteristic)
                            </span>
                        </div>
                        <div v-if="distinctiveSeries.length === 0" class="p-3 text-muted small">
                            Not enough topic mass to compute distinctive topics.
                        </div>
                        <v-chart
                            v-else
                            :option="distinctiveOption"
                            :autoresize="true"
                            @click="onDistinctiveClick"
                            :style="`width: 100%; height: ${distinctiveChartHeight}px`"
                        ></v-chart>
                    </div>
                </div>

                <div class="col-lg-4">
                    <div class="card shadow-sm h-100">
                        <div class="card-header">
                            Most similar {{ fieldLabelPlural }}
                            <span class="text-muted small ms-2">(by topic distribution)</span>
                        </div>
                        <div
                            v-if="!profile.peers || profile.peers.length === 0"
                            class="p-3 text-muted small"
                        >
                            No peers available for this field.
                        </div>
                        <ul v-else class="list-group list-group-flush">
                            <li
                                v-for="peer in profile.peers"
                                :key="peer[0]"
                                class="list-group-item peer-item"
                                @click="goToPeer(peer[0])"
                            >
                                <div class="d-flex justify-content-between align-items-start">
                                    <span class="peer-name">{{ peer[0] }}</span>
                                    <span class="badge rounded-pill bg-secondary ms-2">
                                        {{ peer[1].toFixed(2) }}
                                    </span>
                                </div>
                                <div class="peer-topics">
                                    <span
                                        v-for="tid in peer[2]"
                                        :key="tid"
                                        class="topic-pill"
                                        :style="`background-color: ${topicColor(tid)}`"
                                        :title="topicLabel(tid)"
                                    >{{ topicLabel(tid) }}</span>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            <div class="row g-3 mt-1" v-if="hasTrajectory">
                <div class="col-12">
                    <div class="card shadow-sm">
                        <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
                            <span>Topical trajectory</span>
                            <div class="form-check form-switch small m-0">
                                <input
                                    class="form-check-input"
                                    type="checkbox"
                                    id="baselineToggle"
                                    v-model="showBaseline"
                                />
                                <label class="form-check-label" for="baselineToggle">
                                    Overlay corpus baseline
                                </label>
                            </div>
                        </div>
                        <v-chart
                            :option="trajectoryOption"
                            :autoresize="true"
                            style="width: 100%; height: 340px"
                        ></v-chart>
                    </div>
                </div>
            </div>

            <div class="row g-3 mt-1" v-if="profile.exemplars && profile.exemplars.length">
                <div class="col-lg-8">
                    <div class="card shadow-sm">
                        <div class="card-header">
                            Exemplar passages per top topic
                            <span class="text-muted small ms-2">
                                (the single highest-weighted chunk in {{ profile.field_value }}'s works)
                            </span>
                        </div>
                        <div class="accordion accordion-flush" id="exemplarAccordion">
                            <div
                                v-for="(ex, idx) in profile.exemplars"
                                :key="ex.topic_id + '-' + ex.doc_id"
                                class="accordion-item"
                            >
                                <h2 class="accordion-header">
                                    <button
                                        class="accordion-button collapsed"
                                        type="button"
                                        data-bs-toggle="collapse"
                                        :data-bs-target="`#exemplar-${idx}`"
                                    >
                                        <span
                                            class="topic-swatch me-2"
                                            :style="`background-color: ${topicColor(ex.topic_id)}`"
                                        ></span>
                                        <span class="flex-grow-1">
                                            <b class="exemplar-topic">{{ topicLabel(ex.topic_id) }}</b>
                                            <span
                                                class="text-muted ms-2"
                                                @click.stop="goToTopic(ex.topic_id)"
                                                title="Open topic view"
                                            >(topic {{ ex.topic_id }})</span>
                                        </span>
                                        <span class="badge bg-secondary me-3">
                                            weight {{ ex.weight.toFixed(3) }}
                                        </span>
                                    </button>
                                </h2>
                                <div
                                    :id="`exemplar-${idx}`"
                                    class="accordion-collapse collapse"
                                >
                                    <div class="accordion-body">
                                        <div class="exemplar-citation mb-2">
                                            <citations
                                                :doc="exemplarDoc(ex)"
                                                :philo-db="`${ex.metadata.philo_db}`"
                                            ></citations>
                                        </div>
                                        <div class="exemplar-html" v-html="ex.html"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-lg-4">
                    <div class="card shadow-sm h-100">
                        <div class="card-header">
                            Unusual works
                            <span class="text-muted small ms-2">(farthest from own topic centroid)</span>
                        </div>
                        <div
                            v-if="!profile.anomalies || profile.anomalies.length === 0"
                            class="p-3 text-muted small"
                        >
                            Not enough documents to flag outliers.
                        </div>
                        <ul v-else class="list-group list-group-flush">
                            <li
                                v-for="a in profile.anomalies"
                                :key="a.doc_id"
                                class="list-group-item"
                            >
                                <citations
                                    :doc="exemplarDoc(a)"
                                    :philo-db="`${a.metadata.philo_db}`"
                                ></citations>
                                <span class="badge rounded-pill bg-secondary float-end">
                                    {{ a.distance.toFixed(2) }}
                                </span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </template>

        <!-- Fallback: profile couldn't be built (e.g. value with <2 docs, year
             field, or older DB without the profile pass). Fall back to the
             pre-existing summary table. -->
        <template v-else>
            <topic-distributions v-if="fallbackTopics.length" :topics="fallbackTopics"></topic-distributions>
            <div v-else class="text-center text-muted mt-5">
                No data available for this value.
            </div>
        </template>
    </div>
</template>

<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations.vue";
import TopicDistributions from "./TopicDistributions.vue";

export default {
    name: "FieldDistribution",
    components: { Citations, TopicDistributions },
    data() {
        return {
            loading: true,
            profile: null,
            fallbackTopics: [],
            showBaseline: true,
            topicData,
        };
    },
    computed: {
        fieldName() {
            return this.$route.params.fieldName;
        },
        fieldValue() {
            return this.$route.params.fieldValue;
        },
        fieldLabel() {
            // Human-friendly singular. Good enough for common cases; fall back
            // to the raw column name.
            const overrides = { author: "Author", text_genre: "Genre",
                                publisher: "Publisher", pub_place: "Place of publication",
                                collection: "Collection", editor: "Editor",
                                pub_date: "Publication date" };
            return overrides[this.fieldName] || this.fieldName;
        },
        fieldLabelPlural() {
            const overrides = {
                author: "authors", text_genre: "genres",
                publisher: "publishers", pub_place: "places",
                collection: "collections", editor: "editors",
                pub_date: "dates",
            };
            return overrides[this.fieldName] || `${this.fieldName}s`;
        },
        focusLabel() {
            if (!this.profile) return "";
            const f = this.profile.focus_score;
            let tag;
            if (f >= 0.35) tag = "Specialist";
            else if (f >= 0.15) tag = "Moderate";
            else tag = "Generalist";
            return `${tag} · focus ${f.toFixed(2)}`;
        },
        focusTooltip() {
            return (
                "Focus = 1 − normalized entropy of the topic distribution. " +
                "Higher means most mass concentrates on a few topics."
            );
        },
        distinctiveSeries() {
            return (this.profile && this.profile.distinctive_topics) || [];
        },
        distinctiveChartHeight() {
            // One row per topic + padding; cap around the chart's natural size.
            const n = this.distinctiveSeries.length;
            return Math.max(220, 32 * n + 60);
        },
        distinctiveOption() {
            const rows = [...this.distinctiveSeries].reverse(); // top at top
            const categories = rows.map(([tid]) => this.topicLabel(tid));
            const tids = rows.map(([tid]) => tid);
            const lifts = rows.map(([, , lift]) => lift);
            const weights = rows.map(([, w]) => w);
            // Distinct categorical palette — same rationale as the trajectory
            // chart. The stable per-topic hues can collide when the value's
            // distinctive topics happen to cluster in one part of the wheel.
            const PALETTE = [
                "#5470c6", "#ee6666", "#91cc75", "#fac858",
                "#73c0de", "#9a60b4", "#fc8452", "#3ba272",
                "#c23531", "#61a0a8",
            ];
            // `rows` is top-at-top (original list reversed). Assign palette
            // from bottom up so the top distinctive topic gets the first
            // palette color when read top→bottom.
            const colors = rows.map((_, i) => PALETTE[(rows.length - 1 - i) % PALETTE.length]);
            return {
                animation: false,
                grid: { left: 10, right: 30, top: 10, bottom: 30, containLabel: true },
                xAxis: {
                    type: "value",
                    name: "lift vs corpus",
                    nameLocation: "middle",
                    nameGap: 22,
                    splitLine: { lineStyle: { color: "#eee" } },
                },
                yAxis: {
                    type: "category",
                    data: categories,
                    axisLabel: {
                        fontSize: 12,
                        formatter: (val) => (val.length > 38 ? val.slice(0, 36) + "…" : val),
                    },
                    axisTick: { show: false },
                },
                tooltip: {
                    trigger: "axis",
                    axisPointer: { type: "shadow" },
                    formatter: (params) => {
                        const p = params[0];
                        const idx = p.dataIndex;
                        return `${categories[idx]}<br/>` +
                               `lift: ${lifts[idx].toFixed(2)}×<br/>` +
                               `weight: ${weights[idx].toFixed(3)}`;
                    },
                },
                series: [
                    {
                        type: "bar",
                        data: lifts.map((l, i) => ({
                            value: l,
                            itemStyle: { color: colors[i] },
                        })),
                        barMaxWidth: 22,
                    },
                ],
            };
        },
        hasTrajectory() {
            const t = this.profile && this.profile.trajectory;
            return t && t.years && t.years.length >= 3;
        },
        trajectoryYearRange() {
            const t = this.profile && this.profile.trajectory;
            if (!t || !t.years || !t.years.length) return "";
            return `${t.years[0]}–${t.years[t.years.length - 1]}`;
        },
        trajectoryOption() {
            const t = this.profile.trajectory;
            const years = t.years.map((y) => String(y));
            const tids = Object.keys(t.topics);
            // Distinct categorical palette for the lines in this chart.
            // The global per-topic hue is optimized for stability across views,
            // not for separating any arbitrary group of 6-8 topics that happen
            // to land in the same hue band — so here we trade cross-view color
            // consistency for readability, since the whole point of trajectory
            // is telling lines apart visually.
            const PALETTE = [
                "#5470c6", "#ee6666", "#91cc75", "#fac858",
                "#73c0de", "#9a60b4", "#fc8452", "#3ba272",
            ];
            const series = [];
            for (let i = 0; i < tids.length; i += 1) {
                const tid = tids[i];
                const color = PALETTE[i % PALETTE.length];
                series.push({
                    name: this.topicLabel(tid),
                    type: "line",
                    data: t.topics[tid],
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 2, color },
                    itemStyle: { color },
                });
                if (this.showBaseline && t.baseline && t.baseline[tid]) {
                    series.push({
                        name: `${this.topicLabel(tid)} (corpus)`,
                        type: "line",
                        data: t.baseline[tid],
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, color, type: "dashed", opacity: 0.5 },
                        itemStyle: { color, opacity: 0.5 },
                    });
                }
            }
            return {
                animation: false,
                grid: { left: 40, right: 20, top: 40, bottom: 40, containLabel: true },
                legend: {
                    top: 0,
                    textStyle: { fontSize: 11 },
                    type: "scroll",
                    data: series.filter((s) => !s.name.endsWith("(corpus)")).map((s) => s.name),
                },
                xAxis: {
                    type: "category",
                    data: years,
                    boundaryGap: false,
                },
                yAxis: {
                    type: "value",
                    axisLabel: {
                        formatter: (val) => (typeof val === "number" ? val.toFixed(2) : String(val)),
                    },
                },
                tooltip: { trigger: "axis" },
                series,
            };
        },
    },
    created() {
        this.fetchData();
    },
    watch: {
        $route: "fetchData",
    },
    methods: {
        fetchData() {
            this.loading = true;
            this.profile = null;
            this.fallbackTopics = [];
            const url =
                `${this.$globalConfig.apiServer}/get_metadata_profile/` +
                `${this.$globalConfig.databaseName}/${encodeURIComponent(this.fieldName)}` +
                `?value=${encodeURIComponent(this.fieldValue)}`;
            this.$http
                .get(url)
                .then((response) => {
                    this.profile = response.data;
                })
                .catch(() => this.fetchFallback())
                .finally(() => {
                    this.loading = false;
                });
        },
        fetchFallback() {
            // Older DB or value too small — show the simple distribution table.
            const url =
                `${this.$globalConfig.apiServer}/get_field_distribution/` +
                `${this.$globalConfig.databaseName}/${encodeURIComponent(this.fieldName)}` +
                `?value=${encodeURIComponent(this.fieldValue)}`;
            return this.$http.get(url).then((response) => {
                this.fallbackTopics = response.data.topic_distribution || [];
            }).catch(() => {});
        },
        topicLabel(tid) {
            const td = topicData[parseInt(tid)];
            if (!td) return `Topic ${tid}`;
            return td.label || td.description || `Topic ${tid}`;
        },
        topicColor(tid) {
            const td = topicData[parseInt(tid)];
            return (td && td.color) || "#ad4242";
        },
        exemplarDoc(entry) {
            // Adapt profile exemplar/anomaly entries to the shape Citations expects.
            const md = entry.metadata || {};
            return {
                doc_id: entry.doc_id,
                metadata: md,
                philo_id: md[`philo_${md.philo_type}_id`],
                philo_type: md.philo_type,
            };
        },
        goToPeer(value) {
            this.$router.push(
                `/metadata/${this.fieldName}/${encodeURIComponent(value)}`
            );
        },
        goToTopic(tid) {
            this.$router.push(`/topic/${tid}`);
        },
        onDistinctiveClick(params) {
            const rows = [...this.distinctiveSeries].reverse();
            const row = rows[params.dataIndex];
            if (row) this.goToTopic(row[0]);
        },
    },
};
</script>

<style scoped lang="scss">
@use "../assets/styles/theme.module.scss" as theme;

.profile-header h5 {
    font-weight: 500;
}

.focus-badge {
    background-color: #eee;
    color: #444;
    font-weight: 500;
    cursor: help;
}

.peer-item {
    cursor: pointer;
    padding: 0.55rem 0.85rem;

    &:hover {
        background-color: rgba(theme.$link-color, 0.08);
    }
}

.peer-name {
    font-size: 0.92rem;
    line-height: 1.2;
}

.peer-topics {
    margin-top: 0.25rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
}

.topic-pill {
    display: inline-block;
    max-width: 100%;
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    color: #fff;
    font-size: 0.7rem;
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.topic-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.exemplar-topic {
    font-weight: 500;
}

.exemplar-html {
    max-height: 360px;
    overflow-y: auto;
    font-size: 0.92rem;
    line-height: 1.55;
}

:deep(.accordion-button) {
    padding: 0.6rem 1rem;
    font-size: 0.93rem;
}

:deep(.accordion-button:not(.collapsed)) {
    background-color: rgba(theme.$link-color, 0.06);
    color: inherit;
    box-shadow: none;
}
</style>
