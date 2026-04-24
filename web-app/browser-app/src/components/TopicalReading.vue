<template>
    <div class="container-fluid mt-4">
        <h5 class="ps-4 pe-4" style="text-align: center">
            <citations v-if="mainDoc"
                :doc="mainDoc"
                :philo-db="`${mainDoc.metadata.philo_db}`"></citations>
        </h5>
        <doc-tabs></doc-tabs>
        <div v-if="loading" class="text-center py-5">
            <div class="spinner-border" style="width: 4rem; height: 4rem" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
        <div v-else-if="errorMessage" class="alert alert-warning">{{ errorMessage }}</div>
        <div v-else>
            <div class="card shadow-sm mb-3">
                <div class="card-body p-3">
                    <div class="d-flex flex-wrap gap-2 mb-2">
                        <span v-for="tid in docTopTopics" :key="tid" class="legend-chip"
                            :class="{ dim: focusedTopic !== null && focusedTopic !== tid }" :style="chipStyle(tid)"
                            @click="toggleFocus(tid)" :title="topicLabelByName[tid] || `Topic ${tid}`">
                            <span class="swatch" :style="`background: ${colorByTopic[tid]}`"></span>
                            <span class="name">Topic {{ tid }}</span>
                            <small v-if="topicLabelByName[tid]" class="label">
                                {{ topicLabelByName[tid] }}
                            </small>
                        </span>
                        <span v-if="focusedTopic !== null" class="legend-clear" @click="focusedTopic = null">
                            clear focus
                        </span>
                    </div>
                    <v-chart :option="stripOption" :autoresize="true" @click="onStripClick"
                        style="width: 100%; height: 400px"></v-chart>
                    <div class="strip-slider" v-if="windowingEnabled" ref="sliderTrack"
                        @pointerdown="onSliderPointerDown"
                        :aria-label="`Reading window position (chunk ${windowStart + 1} of ${chunks.length})`">
                        <div class="strip-slider-thumb" :style="thumbStyle"></div>
                    </div>
                </div>
            </div>
            <div class="card shadow-sm">
                <div class="card-body reading-body">
                    <div class="window-nav top" v-if="hasBefore">
                        <button type="button" class="btn btn-sm btn-outline-secondary" @click="pageWindow(-1)">
                            ← Previous section
                        </button>
                    </div>
                    <div v-for="(chunk, offset) in visibleChunks" :key="windowStart + offset"
                        :id="`chunk-${windowStart + offset}`" class="chunk" :class="{
                            dim: isChunkDimmed(chunk),
                            highlighted: highlightedChunk === windowStart + offset,
                        }" :style="chunkStyle(chunk)">
                        <div class="chunk-topics" v-if="chunk.top_topics && chunk.top_topics.length">
                            <span v-for="[tid, w] in chunk.top_topics.slice(0, 3)" :key="tid" class="chunk-topic-pill"
                                :style="`border-color: ${colorByTopic[tid]}`">
                                <span class="swatch" :style="`background: ${colorByTopic[tid]}`"></span>
                                <span class="name">Topic {{ tid }}<template v-if="topicLabelByName[tid]">: {{
                                    topicLabelByName[tid] }}</template></span>
                                <small class="weight">{{ Math.round(w * 100) }}%</small>
                            </span>
                        </div>
                        <div class="chunk-html" v-html="chunk.html"></div>
                    </div>
                    <div class="window-nav bottom" v-if="hasAfter">
                        <button type="button" class="btn btn-sm btn-outline-secondary" @click="pageWindow(1)">
                            Next section →
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import topicData from "../../topic_words.json";
import DocTabs from "./DocTabs.vue";
import Citations from "./Citations.vue";

export default {
    name: "TopicalReading",
    components: { DocTabs, Citations },
    data() {
        return {
            chunks: [],
            docTopTopics: [],
            mainDoc: null,
            loading: false,
            errorMessage: "",
            focusedTopic: null,
            topicData,
            colorByTopic: Object.fromEntries(topicData.map(t => [t.name, t.color || "#888"])),
            topicLabelByName: Object.fromEntries(
                topicData.map(t => [t.name, t.label || ""])
            ),
            // Sliding text window. Chunks are paragraph-groups of ≥ 100
            // preprocessed tokens, so one chunk per view is a comfortable
            // reading pass. Re-anchored when the user clicks a region in
            // the strip chart or drags the slider cursor below it.
            windowSize: 1,
            windowStart: 0,
            highlightedChunk: null,
        };
    },
    computed: {
        visibleChunks() {
            return this.chunks.slice(this.windowStart, this.windowStart + this.windowSize);
        },
        windowEnd() {
            return Math.min(this.chunks.length, this.windowStart + this.windowSize);
        },
        hasBefore() {
            return this.windowStart > 0;
        },
        hasAfter() {
            return this.windowStart + this.windowSize < this.chunks.length;
        },
        windowingEnabled() {
            return this.chunks.length > this.windowSize;
        },
        stripOption() {
            if (!this.chunks.length || !this.docTopTopics.length) return {};
            const data = this.chunks.map((_, i) => String(i + 1));
            return {
                animation: false,
                grid: { left: 10, right: 10, top: 15, bottom: 30, containLabel: true },
                xAxis: {
                    type: "category",
                    data,
                    boundaryGap: false,

                    axisTick: { length: 12 },
                    axisLabel: { hideOverlap: true, margin: 14 },
                },
                yAxis: { type: "value", show: false, max: 1 },
                tooltip: {
                    trigger: "axis",
                    axisPointer: { type: "line" },
                    formatter: (params) => {
                        const idx = params[0].dataIndex;
                        const lines = [`Chunk ${idx + 1}`];
                        for (const p of params) {
                            if (p.value > 0.005) {
                                const tid = parseInt(p.seriesName);
                                const label = this.topicLabelByName[tid] || "";
                                lines.push(
                                    `<span style="color:${p.color}">●</span> `
                                    + `Topic ${tid}${label ? ` · ${label}` : ""}: `
                                    + `${(p.value * 100).toFixed(1)}%`
                                );
                            }
                        }
                        return lines.join("<br/>");
                    },
                },
                series: this.docTopTopics.map((tid, seriesIdx) => {
                    const base = {
                        name: String(tid),
                        type: "line",
                        stack: "total",
                        smooth: true,
                        showSymbol: false,
                        areaStyle: {
                            opacity: this.focusedTopic === null || this.focusedTopic === tid ? 0.65 : 0.1,
                            color: this.colorByTopic[tid],
                        },
                        lineStyle: { width: 0 },
                        itemStyle: { color: this.colorByTopic[tid] },
                        data: this.chunks.map((c) => {
                            const entry = c.top_topics.find(([id]) => id === tid);
                            return entry ? entry[1] : 0;
                        }),
                    };
                    // Draw the current reading window as a translucent overlay
                    // rectangle on the first series only. markArea is defined
                    // once so it doesn't multiply with the stacked series.
                    if (seriesIdx === 0 && this.windowingEnabled) {
                        base.markArea = {
                            silent: true,
                            itemStyle: {
                                color: "rgba(173, 66, 66, 0.18)",
                                borderColor: "#ad4242",
                                borderWidth: 1,
                            },
                            label: { show: false },
                            data: [[
                                { xAxis: String(this.windowStart + 1) },
                                { xAxis: String(Math.min(this.chunks.length, this.windowStart + this.windowSize)) },
                            ]],
                        };
                    }
                    return base;
                }),
            };
        },
        sliderMax() {
            return Math.max(0, this.chunks.length - this.windowSize);
        },
        thumbStyle() {
            // Emit only the window-position fraction as a CSS variable; the
            // thumb's size, shape, and calc() for `left` all live in CSS.
            const fraction = this.sliderMax > 0 ? this.windowStart / this.sliderMax : 0;
            return { "--thumb-fraction": fraction };
        },
    },
    watch: {
        $route: "fetchData",
    },
    created() {
        // Bind once so addEventListener/removeEventListener see the same fn.
        this._onSliderPointerMove = this.onSliderPointerMove.bind(this);
        this._onSliderPointerUp = this.onSliderPointerUp.bind(this);
    },
    beforeUnmount() {
        this.onSliderPointerUp();
    },
    mounted() {
        this.fetchData();
    },
    methods: {
        fetchData() {
            this.loading = true;
            this.errorMessage = "";
            const philoDb = this.$route.params.philoDb;
            const philoId = this.$route.params.doc.split("/").join(" ");
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_doc_topical_reading/${this.$globalConfig.databaseName}/${philoDb}`,
                    { params: { philo_id: philoId } }
                )
                .then((response) => {
                    this.chunks = response.data.chunks || [];
                    this.docTopTopics = response.data.doc_top_topics || [];
                    const metadata = response.data.metadata || null;
                    this.mainDoc = metadata
                        ? {
                            metadata,
                            doc_id: "",
                            philo_id: metadata.philo_id,
                            philo_type: metadata.philo_type,
                        }
                        : null;
                    // Reset the window to the start of the new doc. If the doc
                    // is short enough to fit, expand the window to cover it.
                    this.windowStart = 0;
                    this.highlightedChunk = null;
                    if (this.chunks.length && this.chunks.length <= this.windowSize) {
                        this.windowSize = this.chunks.length;
                    } else {
                        this.windowSize = 1;
                    }
                })
                .catch((error) => {
                    const detail = error?.response?.data?.detail;
                    this.errorMessage = detail
                        ? `Topical reading unavailable: ${detail}`
                        : "Topical reading unavailable for this document.";
                })
                .finally(() => {
                    this.loading = false;
                });
        },
        hexToRgba(hex, alpha) {
            // Accepts #rrggbb; returns "rgba(r,g,b,a)".
            if (!hex || hex[0] !== "#" || hex.length !== 7) {
                return `rgba(136,136,136,${alpha})`;
            }
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return `rgba(${r},${g},${b},${alpha})`;
        },
        chunkStyle(chunk) {
            if (!chunk.top_topics || !chunk.top_topics.length) return {};
            const [dominantId, weight] = chunk.top_topics[0];
            const color = this.colorByTopic[dominantId];
            if (!color) return {};
            // Alpha proportional to dominance — strong claims pop, mixed chunks fade.
            // Floor of 0 at weight=0.15 (≈1/K for K=6), ceiling of 0.5 at weight=1.
            const alpha = Math.max(0, Math.min(0.5, (weight - 0.15) * 0.9));
            return { backgroundColor: this.hexToRgba(color, alpha) };
        },
        chipStyle(tid) {
            return { borderColor: this.colorByTopic[tid] };
        },
        toggleFocus(tid) {
            this.focusedTopic = this.focusedTopic === tid ? null : tid;
        },
        isChunkDimmed(chunk) {
            if (this.focusedTopic === null) return false;
            if (!chunk.top_topics || !chunk.top_topics.length) return true;
            return chunk.top_topics[0][0] !== this.focusedTopic;
        },
        onStripClick(params) {
            if (params?.componentType !== "series") return;
            const idx = params.dataIndex;
            this.recenterWindow(idx);
            this.highlightedChunk = idx;
            // Once the new window has rendered, scroll it into the middle of
            // the body card — makes the "jump" feel responsive.
            this.$nextTick(() => {
                const el = document.getElementById(`chunk-${idx}`);
                if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
            });
        },
        onSliderPointerMove(event) {
            if (!this.$refs.sliderTrack || this._dragAnchorX == null) return;
            const rect = this.$refs.sliderTrack.getBoundingClientRect();
            const usable = rect.width - 30;
            if (usable <= 0 || this.sliderMax <= 0) return;
            const delta = event.clientX - this._dragAnchorX;
            const chunksDelta = (delta / usable) * this.sliderMax;
            const next = Math.round(this._dragAnchorStart + chunksDelta);
            this.windowStart = Math.max(0, Math.min(this.sliderMax, next));
        },
        onSliderPointerUp() {
            this._dragAnchorX = null;
            document.removeEventListener("pointermove", this._onSliderPointerMove);
            document.removeEventListener("pointerup", this._onSliderPointerUp);
            document.removeEventListener("pointercancel", this._onSliderPointerUp);
        },
        onSliderPointerDown(event) {
            if (!this.$refs.sliderTrack) return;
            event.preventDefault();
            const rect = this.$refs.sliderTrack.getBoundingClientRect();
            const usable = rect.width - 30;
            if (usable <= 0 || this.sliderMax <= 0) return;
            // Click anywhere on the track centers the thumb on that point —
            // except inside the thumb, where we skip the jump and just grab.
            const localX = event.clientX - rect.left;
            const fraction = this.windowStart / this.sliderMax;
            const thumbLeft = fraction * usable;
            const thumbRight = thumbLeft + 30;
            if (localX < thumbLeft || localX > thumbRight) {
                const targetFraction = Math.max(0, Math.min(1, (localX - 15) / usable));
                this.windowStart = Math.round(targetFraction * this.sliderMax);
            }
            this._dragAnchorX = event.clientX;
            this._dragAnchorStart = this.windowStart;
            document.addEventListener("pointermove", this._onSliderPointerMove);
            document.addEventListener("pointerup", this._onSliderPointerUp);
            document.addEventListener("pointercancel", this._onSliderPointerUp);
        },
        recenterWindow(idx) {
            const half = Math.floor(this.windowSize / 2);
            const maxStart = Math.max(0, this.chunks.length - this.windowSize);
            this.windowStart = Math.max(0, Math.min(maxStart, idx - half));
        },
        pageWindow(direction) {
            const step = Math.max(1, Math.floor(this.windowSize / 2));
            const maxStart = Math.max(0, this.chunks.length - this.windowSize);
            this.windowStart = Math.max(0, Math.min(maxStart, this.windowStart + direction * step));
            this.highlightedChunk = null;
            // Scroll the newly-surfaced chunk to the top of the viewport so the
            // reader lands on the start of the section they just paged to,
            // rather than staying mid-scroll from the previous one.
            this.$nextTick(() => {
                const el = document.getElementById(`chunk-${this.windowStart}`);
                if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
            });
        },
    },
};
</script>

<style scoped lang="scss">
@use "../assets/styles/theme.module.scss" as theme;

.legend-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.15rem 0.6rem;
    border: 1px solid transparent;
    border-radius: 9999px;
    font-size: 0.8rem;
    cursor: pointer;
    background: #fafafa;
    transition: opacity 0.15s ease;
}

.legend-chip.dim {
    opacity: 0.35;
}

.legend-chip .swatch {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.legend-chip .name {
    font-weight: 600;
}

.legend-chip .label {
    color: #555;
    margin-left: 0.25rem;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.legend-clear {
    font-size: 0.75rem;
    color: #666;
    cursor: pointer;
    align-self: center;
    text-decoration: underline dotted;
}

.reading-body {
    line-height: 1.85;
    font-size: 1.02rem;
    font-family: Georgia, "Times New Roman", serif;
    padding: 1.25rem 1.5rem !important;
}

.chunk {
    /* Block-level since each chunk now renders paragraph HTML from
       PhiloLogic (p, em, sup, footnote refs, etc). */
    display: block;
    transition: background-color 0.15s ease, opacity 0.15s ease;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

.chunk :deep(p) {
    margin-bottom: 0.5rem;
}

.chunk :deep(p:last-child) {
    margin-bottom: 0;
}

// ---------------------------------------------------------------------------
// Deep rules ported from text-pair's textNavigation component. These style
// the PhiloLogic-rendered XML markup that ships inside each chunk's HTML —
// page breaks, speaker/stage directions for drama, line groups for verse,
// dictionary-entry formatting, notes, tables, inline images. Scoped under
// `.chunk` so they only touch the reading body, not the strip chart or
// legend. Rules that referenced ids not present here (book-page,
// bibliographic-results, full-size-image) and alignment-passage classes
// have been omitted.
// ---------------------------------------------------------------------------

.chunk :deep(.xml-pb) {
    display: block;
    text-align: center;
    margin: 10px;
}

.chunk :deep(.xml-pb::before) {
    content: "-" attr(n) "-";
    white-space: pre;
}

.chunk :deep(.highlight) {
    background-color: red;
    color: #fff;
}

.chunk :deep(.xml-div1::after),
.chunk :deep(.xml-div2::after),
.chunk :deep(.xml-div3::after) {
    content: "";
    display: block;
    clear: right;
}

/* Theater */
.chunk :deep(.xml-castitem::after) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(.xml-castlist > .xml-castitem:first-of-type::before) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(.xml-castgroup::before) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(b.headword) {
    font-weight: 700 !important;
    font-size: 130%;
    font-variant: small-caps;
    display: block;
    margin-top: 20px;
}

.chunk :deep(b.headword::before) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(.xml-lb),
.chunk :deep(.xml-l) {
    text-align: justify;
    display: block;
}

.chunk :deep(.xml-sp .xml-lb:first-of-type) {
    content: "";
    white-space: normal;
}

.chunk :deep(.xml-lb[type="hyphenInWord"]) {
    display: inline;
}

.chunk :deep(.xml-sp) {
    display: block;
}

.chunk :deep(.xml-sp::before) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(.xml-stage + .xml-sp:nth-of-type(n + 2)::before) {
    content: "";
}

.chunk :deep(.xml-fw),
.chunk :deep(.xml-join) {
    display: none;
}

.chunk :deep(.xml-speaker + .xml-stage::before) {
    content: "";
    white-space: normal;
}

.chunk :deep(.xml-stage) {
    font-style: italic;
}

.chunk :deep(.xml-stage::after) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(div1 div2::before) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(.xml-speaker) {
    font-weight: 700;
}

/* Verse */
.chunk :deep(.xml-lg) {
    display: block;
}

.chunk :deep(.xml-lg::after) {
    content: "\A";
    white-space: pre;
}

.chunk :deep(.xml-lg:first-of-type::before) {
    content: "\A";
    white-space: pre;
}

/* Front matter / title pages */
.chunk :deep(.xml-castList .xml-front),
.chunk :deep(.xml-castItem),
.chunk :deep(.xml-docTitle),
.chunk :deep(.xml-docImprint),
.chunk :deep(.xml-performance),
.chunk :deep(.xml-docAuthor),
.chunk :deep(.xml-docDate),
.chunk :deep(.xml-premiere),
.chunk :deep(.xml-casting),
.chunk :deep(.xml-recette),
.chunk :deep(.xml-nombre) {
    display: block;
}

.chunk :deep(.xml-docTitle) {
    font-style: italic;
    font-weight: bold;
}

.chunk :deep(.xml-docAuthor),
.chunk :deep(.xml-docTitle),
.chunk :deep(.xml-docDate) {
    text-align: center;
}

.chunk :deep(.xml-docTitle span[type="main"]) {
    font-size: 150%;
    display: block;
}

.chunk :deep(.xml-docTitle span[type="sub"]) {
    font-size: 120%;
    display: block;
}

.chunk :deep(.xml-performance),
.chunk :deep(.xml-docImprint) {
    margin-top: 10px;
}

.chunk :deep(.xml-set) {
    display: block;
    font-style: italic;
    margin-top: 10px;
}

/* Dictionary formatting */
.chunk {
    counter-reset: section;
}

.chunk :deep(.xml-prononciation::before) {
    content: "(";
}

.chunk :deep(.xml-prononciation::after) {
    content: ")\A";
}

.chunk :deep(.xml-nature) {
    font-style: italic;
}

.chunk :deep(.xml-indent),
.chunk :deep(.xml-variante) {
    display: block;
}

.chunk :deep(.xml-variante) {
    padding-top: 10px;
    padding-bottom: 10px;
    text-indent: -1.3em;
    padding-left: 1.3em;
}

.chunk :deep(.xml-variante::before) {
    counter-increment: section;
    content: counter(section) ")\00a0";
    font-weight: 700;
}

.chunk :deep(:not(.xml-rubrique) + .xml-indent) {
    padding-top: 10px;
}

.chunk :deep(.xml-indent) {
    padding-left: 1.3em;
}

.chunk :deep(.xml-cit) {
    padding-left: 2.3em;
    display: block;
    text-indent: -1.3em;
}

.chunk :deep(.xml-indent > .xml-cit) {
    padding-left: 1em;
}

.chunk :deep(.xml-cit::before) {
    content: "\2012\00a0\00ab\00a0";
}

.chunk :deep(.xml-cit::after) {
    content: "\00a0\00bb\00a0(" attr(aut) "\00a0" attr(ref) ")";
    font-variant: small-caps;
}

.chunk :deep(.xml-rubrique) {
    display: block;
    margin-top: 20px;
}

.chunk :deep(.xml-rubrique::before) {
    content: attr(nom);
    font-variant: small-caps;
    font-weight: 700;
}

.chunk :deep(.xml-corps + .xml-rubrique) {
    margin-top: 10px;
}

/* Methodique styling */
.chunk :deep(div[type="article"] .headword) {
    display: inline-block;
    margin-bottom: 10px;
}

.chunk :deep(.headword + p) {
    display: inline;
}

.chunk :deep(.headword + p + p) {
    margin-top: 10px;
}

/* Notes */
.chunk :deep(.popover-content .xml-p:not(:first-of-type)) {
    display: block;
    margin-top: 1em;
    margin-bottom: 1em;
}

.chunk :deep(.note-content) {
    display: none;
}

.chunk :deep(.note),
.chunk :deep(.note-ref) {
    vertical-align: 0.3em;
    font-size: 0.7em;
    background-color: theme.$button-color;
    color: #fff !important;
    padding: 0 0.2rem;
    border-radius: 50%;
}

.chunk :deep(.note:hover),
.chunk :deep(.note-ref:hover) {
    cursor: pointer;
    text-decoration: none;
}

.chunk :deep(div[type="notes"] .xml-note) {
    margin: 15px 0px;
    display: block;
}

.chunk :deep(.xml-note::before) {
    content: "note\00a0" attr(n) "\00a0:\00a0";
    font-weight: 700;
}

/* Page images */
.chunk :deep(.xml-pb-image) {
    display: block;
    text-align: center;
    margin: 10px;
}

.chunk :deep(.page-image-link) {
    margin-top: 10px;
    text-align: center;
}

/* Inline images */
.chunk :deep(.inline-img) {
    max-width: 40%;
    float: right;
    height: auto;
    padding-left: 15px;
    padding-top: 15px;
}

.chunk :deep(.inline-img:hover) {
    cursor: pointer;
}

.chunk :deep(.link-back) {
    display: none;
}

.chunk :deep(.xml-add) {
    color: #ef4500;
}

.chunk :deep(.xml-seg) {
    display: block;
}

/* Tables */
.chunk :deep(b.headword[rend="center"]) {
    margin-bottom: 30px;
    text-align: center;
}

.chunk :deep(.xml-table) {
    display: table;
    position: relative;
    text-align: center;
    border-collapse: collapse;
}

.chunk :deep(.xml-table .xml-pb-image) {
    position: absolute;
    width: 100%;
    margin-top: 15px;
}

.chunk :deep(.xml-row) {
    display: table-row;
    font-weight: 700;
    text-align: left;
    min-height: 50px;
    font-variant: small-caps;
    padding-top: 10px;
    padding-bottom: 10px;
    padding-right: 20px;
    border-bottom: #ddd 1px solid;
}

.chunk :deep(.xml-row ~ .xml-row) {
    font-weight: inherit;
    text-align: justify;
    font-variant: inherit;
}

.chunk :deep(.xml-pb-image + .xml-row) {
    padding-top: 50px;
    padding-bottom: 10px;
    border-top-width: 0px;
}

.chunk :deep(.xml-cell) {
    display: table-cell;
    padding-top: inherit;
    padding-bottom: inherit;
}

.chunk :deep(s) {
    text-decoration: none;
}

.chunk :deep(.xml-titlePage) {
    display: none;
}

.chunk :deep(.xml-ref) {
    vertical-align: 0.3em;
    font-size: 0.7em;
    padding: 0 0.2rem;
    border-radius: 50%;
}

.chunk-topics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.6rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px dashed rgba(0, 0, 0, 0.1);
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 0.72rem;
}

.chunk-topic-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.1rem 0.55rem;
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(0, 0, 0, 0.12);
    border-radius: 9999px;
    color: #333;
    line-height: 1.4;
}

.chunk-topic-pill .swatch {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.chunk-topic-pill .name {
    font-weight: 500;
}

.chunk-topic-pill .weight {
    color: #888;
    font-variant-numeric: tabular-nums;
}

.chunk.dim {
    opacity: 0.25;
}

.chunk:hover {
    filter: brightness(0.96);
}

.chunk.highlighted {
    box-shadow: 0 0 0 2px #ad4242, 0 0 0 4px rgba(173, 66, 66, 0.2);
    border-radius: 3px;
    animation: chunk-pulse 1.2s ease-out;
}

@keyframes chunk-pulse {
    0% {
        box-shadow: 0 0 0 0 rgba(173, 66, 66, 0.6);
    }

    100% {
        box-shadow: 0 0 0 2px #ad4242, 0 0 0 4px rgba(173, 66, 66, 0.2);
    }
}

.strip-slider {
    position: relative;
    height: 22px;
    margin: -3.8rem 0.95rem 1rem 2.2rem;
    border-radius: 4px;
    cursor: pointer;
    user-select: none;
    touch-action: none;
}

.strip-slider-thumb {
    position: absolute;
    top: 50%;
    width: 35px;
    height: 10px;
    left: calc(var(--thumb-fraction, 0) * (100% - 30px));
    transform: translateY(-50%);
    background: #ad4242;
    border: 1px solid #8a3434;
    border-radius: 3px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
    /* Pointer events go to the track so clicks inside the thumb start a drag
       rather than nothing — the track's down-handler detects thumb-hit via
       geometry. */
    pointer-events: none;
    transition: box-shadow 0.15s ease;
}

.strip-slider:hover .strip-slider-thumb {
    box-shadow: 0 2px 5px rgba(173, 66, 66, 0.6);
}

.window-nav {
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: system-ui, -apple-system, sans-serif;
    padding: 0.5rem 0;
}

.window-nav.top {
    margin-bottom: 0.75rem;
}

.window-nav.bottom {
    margin-top: 0.75rem;
}
</style>
