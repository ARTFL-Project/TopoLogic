#!/usr/bin/env python3

from abc import ABCMeta, abstractmethod

import numpy as np
from annoy import AnnoyIndex
from multiprocess import cpu_count
from scipy.sparse import coo_matrix, csr_matrix
from sklearn.decomposition import NMF
from sklearn.decomposition import LatentDirichletAllocation as LDA
from sklearn.metrics import pairwise_distances
from tqdm import tqdm


class TopicModel(object):
    __metaclass__ = ABCMeta

    def __init__(self, corpus, max_iter=None):
        self.corpus = corpus  # a Corpus object
        self.document_topic_matrix = None  # document x topic matrix
        self.topic_word_matrix = None  # topic x word matrix
        self.nb_topics = None  # a scalar value > 1
        self.model = None
        self.max_iter = max_iter
        self.annoy_index = None
        self.topic_frequencies = None

    @abstractmethod
    def infer_topics(self, num_topics=10, **kwargs):
        pass

    def _store_matrices(self, topic_document):
        """Pack the fitted estimator's outputs into sparse CSR matrices."""
        self.topic_word_matrix = csr_matrix(self.model.components_)
        self.document_topic_matrix = csr_matrix(np.asarray(topic_document))

    def infer_and_replace(self, corpus):
        """Replace resulting matrices from training with full corpus."""
        self.corpus = corpus
        topic_document = self.model.transform(corpus.sklearn_vector_space)
        self._store_matrices(topic_document)
        self._build_topic_index()

    def _build_topic_index(self):
        """Derive topic frequencies and the doc-topic Annoy index.

        Backend-independent, kept in one place so backends cannot drift.
        """
        topic_sums = np.asarray(self.document_topic_matrix.sum(axis=0)).ravel()
        total = topic_sums.sum()
        self.topic_frequencies = topic_sums / total if total else topic_sums

        self.annoy_index = AnnoyIndex(self.document_topic_matrix.shape[1], "angular")
        for i, doc_vector in tqdm(
            enumerate(self.document_topic_matrix),
            total=self.document_topic_matrix.shape[0],
            desc="Building Annoy index of document-topic vectors",
            leave=False,
        ):
            self.annoy_index.add_item(i, doc_vector.toarray()[0])
        self.annoy_index.build(1000, n_jobs=cpu_count() - 1)

    def fold_in(self, bow, iterations=10):
        """Infer topic weights for unseen rows with the topic-word matrix frozen.

        Scores passages for the reading view. Not `bow @ beta.T`: topic rows
        carry unequal total mass, so that scores large-vocabulary topics higher
        on any passage (43.8% argmax agreement with NMF.transform, weights
        correlating +0.998 with row mass). KL multiplicative updates reach
        97.2% at 10 iterations, one matmul each.

        Returns row-normalized weights, n_rows x n_topics.
        """
        beta = self.topic_word_matrix.toarray().astype(np.float64)
        X = bow.toarray().astype(np.float64) if hasattr(bow, "toarray") else np.asarray(bow, dtype=np.float64)
        if X.size == 0 or beta.size == 0:
            return np.zeros((X.shape[0], beta.shape[0]))
        # Uniform start carrying each row's total mass.
        W = np.repeat(X.sum(axis=1, keepdims=True) / beta.shape[0], beta.shape[0], axis=1)
        # Every row of `ones @ beta.T` is beta.sum(1); broadcast instead.
        beta_col_sums = beta.sum(axis=1)[None, :] + 1e-10
        for _ in range(iterations):
            W *= ((X / (W @ beta + 1e-10)) @ beta.T) / beta_col_sums
        totals = W.sum(axis=1, keepdims=True)
        return W / np.where(totals > 0, totals, 1.0)

    def most_similar_topic_by_doc_distribution(self):
        return pairwise_distances(self.document_topic_matrix.transpose())

    def top_words(self, topic_id, num_words):
        row = self.topic_word_matrix[topic_id].toarray()[0]
        order = np.argsort(row, kind="stable")[::-1][:num_words]
        return [(self.corpus.feature_names[i], float(row[i])) for i in order]

    def top_documents(self, topic_id, num_docs=None):
        col = self.document_topic_matrix[:, topic_id].toarray().ravel()
        order = np.argsort(col, kind="stable")[::-1]
        if num_docs is not None:
            order = order[:num_docs]
        else:
            order = order[col[order] > 0]
        return [(int(i), float(col[i])) for i in order]

    def word_distribution_for_topic(self, topic_id):
        return self.topic_word_matrix[topic_id].toarray()[0]

    def topic_distribution_for_document(self, doc_id):
        return self.document_topic_matrix[doc_id].toarray()[0]

    def topic_distribution_for_word(self, word_id):
        return self.topic_word_matrix[:, word_id].toarray().ravel()

    def get_topic_frequency(self, topic_id):
        return self.topic_frequencies[topic_id]

    def most_likely_topics_for_document(self, doc_id):
        topic_vector = self.topic_distribution_for_document(doc_id)
        topics = np.argsort(topic_vector)
        return zip(topics, (topic_vector[t] for t in topics))


class LatentDirichletAllocation(TopicModel):
    def infer_topics(self, num_topics=10, algorithm="variational", **kwargs):
        self.nb_topics = num_topics
        self.model = LDA(
            n_components=num_topics,
            learning_method="batch",
            n_jobs=-1,
            random_state=0,
            max_iter=self.max_iter,
            doc_topic_prior=1.0 / num_topics,
            topic_word_prior=0.01 / num_topics,
        )
        topic_document = self.model.fit_transform(self.corpus.sklearn_vector_space)
        self._store_matrices(topic_document)


class NonNegativeMatrixFactorization(TopicModel):
    def infer_topics(self, num_topics=10, **kwargs):
        self.nb_topics = num_topics
        self.model = NMF(
            n_components=num_topics,
            init="nndsvda",
            solver="mu",
            beta_loss="kullback-leibler",
            alpha_H=0.00025 * num_topics,  # keeps the top word from dominating
            max_iter=self.max_iter,
            random_state=0,
            verbose=True,
        )
        topic_document = self.model.fit_transform(self.corpus.sklearn_vector_space)
        self._store_matrices(topic_document)


class BERTopicModel(TopicModel):
    """SBERT + UMAP + HDBSCAN + c-TF-IDF via BERTopic.

    Three departures from stock BERTopic, needed to satisfy the topic-model
    contract DB.py expects:

    1. The corpus vocabulary is pinned for c-TF-IDF, so word_ids stay aligned
       with the `words` table.
    2. `document_topic_matrix` is a softmax over cosine similarity to topic
       centroids, not HDBSCAN membership — that is a hard partition in
       probability clothing, and it collapses every mixed-membership consumer
       downstream.
    3. Fitting and inference both operate on chunks; documents are the
       length-weighted mean of their chunks' distributions.
    """

    def __init__(
        self,
        corpus,
        max_iter=None,
        embedding_model="Alibaba-NLP/gte-multilingual-base",
        reduce_outliers=True,
        min_cluster_size=10,
        max_chunk_size=None,
        cluster_selection_method="leaf",
        cluster_selection_epsilon=0.0,
        umap_neighbors=15,
        assignment_temperature=None,
        mmr_diversity=0.0,
        batch_size=32,
    ):
        super().__init__(corpus, max_iter=max_iter)
        self.embedding_model = embedding_model
        self.reduce_outliers = reduce_outliers
        self.min_cluster_size = int(min_cluster_size)
        self.max_chunk_size = max_chunk_size
        self.cluster_selection_method = cluster_selection_method
        self.cluster_selection_epsilon = cluster_selection_epsilon
        self.umap_neighbors = umap_neighbors
        self.assignment_temperature = assignment_temperature
        self.assignment_temperature_ = None  # resolved at fit time
        self.mmr_diversity = mmr_diversity
        self.batch_size = batch_size
        self.topic_centroids_ = None
        self.word_embeddings_ = None
        self.chunk_topic_matrix = None
        self.chunk_doc_index = None
        self.chunk_tokens = None

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def infer_topics(self, num_topics=10, **kwargs):
        from bertopic import BERTopic
        from bertopic.vectorizers import ClassTfidfTransformer
        from sklearn.feature_extraction.text import CountVectorizer

        # Fit on chunks, not documents: a long document's word co-occurrence is
        # nearly uniform, so document-level statistics cannot separate themes
        # that always appear together inside it.
        chunked, embedder = self.corpus.compute_or_load_embeddings(
            self.embedding_model,
            batch_size=self.batch_size,
            max_chunk_size=self.max_chunk_size,
        )
        docs = chunked.texts
        embeddings = chunked.embeddings

        # BERTopic refits its vectorizer on per-topic concatenated docs, which
        # would reset the vocabulary and break word_id alignment with
        # corpus.sklearn_vector_space. A CountVectorizer constructed with
        # vocabulary= no-ops `fit()`, so the corpus vocabulary survives.
        pinned_vectorizer = CountVectorizer(
            vocabulary=self.corpus.vectorizer.vocabulary_,
            ngram_range=self.corpus.ngram,
        )

        umap_model, hdbscan_model = self._build_clustering_backend(len(embeddings))

        # Three sentinels (parsed in config.py): None keeps HDBSCAN's clusters,
        # "auto" merges similar ones, int N reduces agglomeratively. Prefer the
        # first two — agglomerative merging snowballs into one oversized topic,
        # since the largest cluster sits nearest the corpus centroid.
        nr_topics = num_topics
        if isinstance(nr_topics, int):
            print(
                f"Warning: nr_topics={nr_topics} forces agglomerative merging, which "
                "biases toward one oversized topic. Prefer number_of_topics empty or "
                "'auto' and tune min_cluster_size.",
                flush=True,
            )

        # language="multilingual": with "english" BERTopic strips non-ASCII,
        # turning "liberté" into "libert" — absent from the pinned vocabulary,
        # so df=0 and idf=inf. Any other value skips that.
        #
        # No representation_model, deliberately: BERTopic feeds those into
        # `topic_representations_`, never back into `c_tf_idf_`, which is what
        # the persisted matrix reads. Diversification lives in top_words().
        ctfidf_model = ClassTfidfTransformer(
            bm25_weighting=True,
            reduce_frequent_words=True,
        )
        # calculate_probabilities=False: HDBSCAN's all_points_membership_vectors
        # is expensive and nothing consumes it any more -- the doc-topic matrix
        # comes from centroid similarity below.
        self.model = BERTopic(
            embedding_model=embedder,
            language="multilingual",
            vectorizer_model=pinned_vectorizer,
            ctfidf_model=ctfidf_model,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            calculate_probabilities=False,
            nr_topics=nr_topics,
            verbose=True,
        )
        topics, _ = self.model.fit_transform(docs, embeddings=embeddings)
        labels = np.asarray(topics, dtype=int)

        n_outliers = int((labels == -1).sum())
        if n_outliers:
            print(
                f"HDBSCAN left {n_outliers} of {len(labels)} docs as outliers "
                f"({100.0 * n_outliers / len(labels):.1f}%).",
                flush=True,
            )
        if self.reduce_outliers and n_outliers:
            # Not strategy="probabilities", which sends every outlier to its
            # argmax topic and so feeds the densest cluster.
            labels = self._assign_outliers_by_centroid(embeddings, labels)
            self.model.update_topics(docs, topics=labels.tolist(), vectorizer_model=pinned_vectorizer)

        # nb_topics excludes the -1 outlier bucket if it survived.
        topic_ids = sorted(t for t in self.model.get_topics().keys() if t != -1)
        if not topic_ids:
            raise RuntimeError(
                "HDBSCAN produced no clusters -- every document is an outlier. "
                "Lower min_cluster_size or check that the embeddings are meaningful."
            )
        self.nb_topics = len(topic_ids)

        # Centroids come from `labels`, the same partition that fed
        # update_topics and so c_tf_idf_ — keeping both matrices on one
        # clustering rather than two.
        self.topic_centroids_ = self._topic_centroids(embeddings, labels, topic_ids)
        self._store_bertopic_matrices(chunked, topic_ids)
        self._report_topic_sizes(labels, topic_ids)

        if self.mmr_diversity > 0:
            # While the embedder is still alive; top_words() needs these later.
            print(f"Embedding {len(self.corpus.feature_names)} vocabulary terms for MMR...", flush=True)
            self.word_embeddings_ = embedder.encode(
                list(self.corpus.feature_names),
                batch_size=self.batch_size,
                show_progress_bar=True,
                convert_to_numpy=True,
            )

        # Free the embedder + BERTopic's wrapper around it now that
        # representation is fully baked. Downstream code (Gemma labeler,
        # cuML clustering) gets the VRAM back.
        self.model.embedding_model = None
        del embedder
        import gc
        gc.collect()
        self._empty_cuda_cache()

    def infer_and_replace(self, corpus):
        """Apply the trained BERTopic to a (possibly different) corpus.

        Mirrors the NMF path: the topic-word side stays as trained and only the
        document side is recomputed. Uses the stored centroids, so it needs no
        BERTopic transform — just cosine against them.
        """
        self.corpus = corpus
        chunked, embedder = corpus.compute_or_load_embeddings(
            self.embedding_model,
            batch_size=self.batch_size,
            max_chunk_size=self.max_chunk_size,
        )
        # Nothing here needs the embedder: embeddings are supplied, and the
        # representation was baked during infer_topics.
        del embedder
        self._empty_cuda_cache()

        topic_ids = sorted(t for t in self.model.get_topics().keys() if t != -1)
        self._store_bertopic_matrices(chunked, topic_ids)
        self._build_topic_index()

    # ------------------------------------------------------------------
    # Topic representation
    # ------------------------------------------------------------------

    def top_words(self, topic_id, num_words):
        """c-TF-IDF top words, optionally MMR-diversified.

        At mmr_diversity == 0 this is the base implementation. Above 0, words
        are re-ordered to suppress near-duplicates. Weights stay the true
        c-TF-IDF scores either way, so under MMR they stop decreasing
        monotonically — DB.py feeds them straight into a bar chart, which is
        why this defaults to off.
        """
        if self.mmr_diversity <= 0 or self.word_embeddings_ is None:
            return super().top_words(topic_id, num_words)

        row = self.topic_word_matrix[topic_id].toarray()[0]
        pool = np.argsort(row, kind="stable")[::-1][: max(num_words * 5, 100)]
        pool = pool[row[pool] > 0]
        if len(pool) <= num_words:
            return [(self.corpus.feature_names[i], float(row[i])) for i in pool]

        vecs = np.asarray(self.word_embeddings_[pool], dtype=np.float32)
        vecs = vecs / np.clip(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12, None)
        similarity = vecs @ vecs.T

        relevance = row[pool].astype(np.float64)
        spread = relevance.max() - relevance.min()
        relevance = (relevance - relevance.min()) / spread if spread > 0 else np.ones_like(relevance)

        lam = 1.0 - self.mmr_diversity
        selected = [0]  # the strongest c-TF-IDF word always leads
        candidates = list(range(1, len(pool)))
        while len(selected) < num_words and candidates:
            redundancy = similarity[np.ix_(candidates, selected)].max(axis=1)
            best = candidates[int(np.argmax(lam * relevance[candidates] - (1.0 - lam) * redundancy))]
            selected.append(best)
            candidates.remove(best)
        return [(self.corpus.feature_names[pool[i]], float(row[pool[i]])) for i in selected]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_clustering_backend(self, n_points):
        """Use cuML's GPU UMAP + HDBSCAN when available, else CPU equivalents.

        cuML lives in the `cuda` extra. The import is gated on CUDA actually
        being available at runtime so a CUDA-installed env on a CPU-only
        machine still works.

        Granularity knobs, roughly in order of effect: cluster_selection_method
        ("eom" gives markedly fewer, broader topics than "leaf"), umap_neighbors
        (higher preserves more global structure), min_cluster_size, and
        cluster_selection_epsilon (merges clusters closer than the threshold).
        """
        print(
            f"UMAP/HDBSCAN over {n_points} points: min_cluster_size={self.min_cluster_size}, "
            f"cluster_selection_method={self.cluster_selection_method}, "
            f"n_neighbors={self.umap_neighbors}, "
            f"cluster_selection_epsilon={self.cluster_selection_epsilon}",
            flush=True,
        )
        try:
            import torch
            cuda_available = torch.cuda.is_available()
        except ImportError:
            cuda_available = False

        if cuda_available:
            try:
                from cuml.cluster import HDBSCAN as cuHDBSCAN
                from cuml.manifold import UMAP as cuUMAP
                print("Using cuML GPU UMAP + HDBSCAN.", flush=True)
                return (
                    cuUMAP(
                        n_neighbors=self.umap_neighbors,
                        n_components=5,
                        min_dist=0.0,
                        metric="cosine",
                        random_state=0,
                    ),
                    cuHDBSCAN(
                        min_cluster_size=self.min_cluster_size,
                        metric="euclidean",
                        cluster_selection_method=self.cluster_selection_method,
                        cluster_selection_epsilon=self.cluster_selection_epsilon,
                        prediction_data=True,
                    ),
                )
            except ImportError:
                pass

        from hdbscan import HDBSCAN
        from umap import UMAP
        return (
            UMAP(
                n_neighbors=self.umap_neighbors,
                n_components=5,
                min_dist=0.0,
                metric="cosine",
                random_state=0,
            ),
            HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                metric="euclidean",
                cluster_selection_method=self.cluster_selection_method,
                cluster_selection_epsilon=self.cluster_selection_epsilon,
                prediction_data=True,
            ),
        )

    def _assign_outliers_by_centroid(self, embeddings, labels):
        """Send each -1 doc to the topic whose centroid it is closest to."""
        topic_ids = sorted({int(t) for t in labels if t != -1})
        if not topic_ids:
            return labels
        centroids = self._topic_centroids(embeddings, labels, topic_ids)
        outliers = labels == -1
        similarity = self._cosine_to_centroids(np.asarray(embeddings)[outliers], centroids)
        reassigned = labels.copy()
        reassigned[outliers] = np.asarray(topic_ids)[similarity.argmax(axis=1)]
        return reassigned

    @staticmethod
    def _topic_centroids(embeddings, labels, topic_ids):
        """Mean embedding per topic, in topic_ids order."""
        emb = np.asarray(embeddings, dtype=np.float32)
        labels = np.asarray(labels)
        centroids = np.zeros((len(topic_ids), emb.shape[1]), dtype=np.float32)
        for i, topic_id in enumerate(topic_ids):
            mask = labels == topic_id
            if mask.any():
                centroids[i] = emb[mask].mean(axis=0)
        return centroids

    @staticmethod
    def _cosine_to_centroids(embeddings, centroids):
        emb = np.asarray(embeddings, dtype=np.float32)
        emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-12, None)
        cen = np.asarray(centroids, dtype=np.float32)
        cen = cen / np.clip(np.linalg.norm(cen, axis=1, keepdims=True), 1e-12, None)
        return emb @ cen.T

    @staticmethod
    def _softmax(scores):
        """Row-wise softmax, returned as float64.

        float64 is contractual: np.float64 subclasses Python float so json.dump
        accepts it, np.float32 does not. Upstream cosine math stays float32.
        """
        scores = np.asarray(scores, dtype=np.float64)
        shifted = scores - scores.max(axis=1, keepdims=True)
        exponentiated = np.exp(shifted)
        return exponentiated / np.clip(exponentiated.sum(axis=1, keepdims=True), 1e-12, None)

    # Target logit gap between a document's best and second-best topic when
    # the temperature is auto-calibrated. exp(2.0) ~ 7:1 -- clearly peaked,
    # but leaving real mass on competing topics.
    TARGET_LOGIT_GAP = 2.0

    def _calibrate_temperature(self, similarity):
        """Choose T from the observed top-1 vs top-2 similarity spread.

        Cosine ranges vary widely across models and corpora, so a fixed
        temperature that gives useful mixed membership on one goes one-hot on
        another. The median gap makes peakiness comparable across both.
        """
        if similarity.shape[1] < 2:
            return 1.0
        top_two = np.partition(similarity, -2, axis=1)[:, -2:]
        median_gap = float(np.median(top_two[:, 1] - top_two[:, 0]))
        return max(median_gap / self.TARGET_LOGIT_GAP, 1e-3)

    def _soft_topic_distribution(self, embeddings):
        """Softmax over cosine similarity to topic centroids.

        Replaces HDBSCAN membership vectors, which are near one-hot. Low
        temperature approaches one-hot, high goes to uniform; left unset it is
        calibrated once at fit time and reused so inference matches training.
        """
        similarity = self._cosine_to_centroids(embeddings, self.topic_centroids_)
        if self.assignment_temperature_ is None:
            self.assignment_temperature_ = (
                self.assignment_temperature
                if self.assignment_temperature is not None
                else self._calibrate_temperature(similarity)
            )
            entropy = self._mean_entropy(self._softmax(similarity / self.assignment_temperature_))
            print(
                f"Doc-topic temperature {self.assignment_temperature_:.4f} "
                f"({'configured' if self.assignment_temperature is not None else 'auto-calibrated'}); "
                f"mean entropy {entropy:.3f} of {np.log(similarity.shape[1]):.3f} max.",
                flush=True,
            )
        return self._softmax(similarity / self.assignment_temperature_)

    @staticmethod
    def _mean_entropy(distribution):
        return float(-(distribution * np.log(np.clip(distribution, 1e-12, None))).sum(axis=1).mean())

    @staticmethod
    def _aggregate_chunks_to_docs(chunk_distributions, doc_index, tokens, n_docs):
        """Length-weighted mean of each document's chunk distributions.

        A convex combination of distributions is a distribution, unlike the
        mean of unit vectors. Length weighting is the analogue of bag-of-words
        additivity. One sparse matmul, not np.add.at.
        """
        weights = np.asarray(tokens, dtype=np.float64)
        weights = np.where(weights > 0, weights, 1.0)
        n_chunks = len(doc_index)
        scatter = coo_matrix(
            (weights, (np.asarray(doc_index), np.arange(n_chunks))),
            shape=(n_docs, n_chunks),
        ).tocsr()
        totals = np.asarray(scatter.sum(axis=1)).ravel()
        totals = np.where(totals > 0, totals, 1.0)
        return np.asarray(scatter @ chunk_distributions) / totals[:, None]

    def _store_bertopic_matrices(self, chunked, topic_ids):
        # c_tf_idf_ rows are ordered by BERTopic's internal topic id (-1 first
        # if present, then 0..N). Slice out the real topics in our chosen order.
        all_topic_ids = sorted(self.model.get_topics().keys())
        row_index = {tid: i for i, tid in enumerate(all_topic_ids)}
        row_order = [row_index[tid] for tid in topic_ids]
        self.topic_word_matrix = csr_matrix(self.model.c_tf_idf_[row_order])

        # Score each chunk, then aggregate. The chunk distributions are what
        # the reading view shows, so a document's distribution is by
        # construction the weighted mean of what a reader sees.
        self.chunk_topic_matrix = self._soft_topic_distribution(chunked.embeddings)
        self.chunk_doc_index = chunked.doc_index
        self.chunk_tokens = chunked.tokens
        self.document_topic_matrix = csr_matrix(
            self._aggregate_chunks_to_docs(
                self.chunk_topic_matrix, chunked.doc_index, chunked.tokens, self.corpus.size
            )
        )

    def _report_topic_sizes(self, labels, topic_ids):
        """Print size skew against uniform, since 33% is balanced across 3
        topics and a severe mega-topic across 100.
        """
        counts = np.asarray([(labels == topic_id).sum() for topic_id in topic_ids], dtype=float)
        share = counts / max(counts.sum(), 1.0)
        uniform = 1.0 / len(topic_ids)
        skew = share.max() / uniform
        order = np.argsort(share)[::-1]
        top = ", ".join(f"t{topic_ids[i]}={share[i]:.1%}" for i in order[:5])
        print(
            f"{len(topic_ids)} topics; largest share {share.max():.1%} "
            f"= {skew:.1f}x uniform ({uniform:.1%}). Top 5: {top}",
            flush=True,
        )
        if skew > 5.0:
            print(
                f"Warning: largest topic is {skew:.1f}x its uniform share. Try raising "
                "min_cluster_size, or leaving number_of_topics empty if it is set to an int.",
                flush=True,
            )

    @staticmethod
    def _empty_cuda_cache():
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
