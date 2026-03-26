"""Tests for embedding+NLI graph edge builder."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from app.tasks.graph_tasks import (
    find_knee_threshold,
    classify_relationship,
    build_candidate_pairs,
    run_nli_causal,
)


class TestFindKneeThreshold:
    def test_clear_knee_in_bimodal_distribution(self):
        rng = np.random.default_rng(42)
        signal = rng.uniform(0.75, 0.95, size=20)
        noise = rng.uniform(0.05, 0.30, size=80)
        similarities = np.concatenate([signal, noise])
        threshold = find_knee_threshold(similarities)
        assert 0.20 < threshold < 0.95

    def test_uniform_distribution_returns_fallback(self):
        similarities = np.random.uniform(0.0, 1.0, size=100)
        threshold = find_knee_threshold(similarities, fallback=0.65)
        assert isinstance(threshold, float)
        assert 0.0 < threshold < 1.0

    def test_empty_similarities_returns_fallback(self):
        threshold = find_knee_threshold(np.array([]), fallback=0.65)
        assert threshold == 0.65

    def test_all_identical_returns_fallback(self):
        similarities = np.full(50, 0.5)
        threshold = find_knee_threshold(similarities, fallback=0.65)
        assert isinstance(threshold, float)

    def test_threshold_is_between_0_and_1(self):
        sims = np.random.uniform(0.2, 0.9, size=200)
        threshold = find_knee_threshold(sims)
        assert 0.0 < threshold < 1.0


class TestClassifyRelationship:
    def test_high_entailment_returns_causes(self):
        scores = {"entailment": 0.85, "contradiction": 0.05, "neutral": 0.10}
        assert classify_relationship(scores) == "causes"

    def test_medium_entailment_returns_amplifies(self):
        scores = {"entailment": 0.60, "contradiction": 0.10, "neutral": 0.30}
        assert classify_relationship(scores) == "amplifies"

    def test_high_contradiction_returns_mitigates(self):
        scores = {"entailment": 0.10, "contradiction": 0.70, "neutral": 0.20}
        assert classify_relationship(scores) == "mitigates"

    def test_neutral_dominant_returns_correlates(self):
        scores = {"entailment": 0.35, "contradiction": 0.10, "neutral": 0.55}
        assert classify_relationship(scores) == "correlates"

    def test_low_entailment_returns_precedes(self):
        scores = {"entailment": 0.25, "contradiction": 0.10, "neutral": 0.65}
        assert classify_relationship(scores) == "precedes"


class TestBuildCandidatePairs:
    def test_pairs_above_threshold_are_returned(self):
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.99, 0.1, 0.0],
            [0.0, 0.0, 1.0],
        ])
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        pairs = build_candidate_pairs(embeddings, threshold=0.8)
        assert len(pairs) == 1
        assert pairs[0][0] == 0 and pairs[0][1] == 1

    def test_no_self_pairs(self):
        embeddings = np.eye(3)
        pairs = build_candidate_pairs(embeddings, threshold=0.0)
        for i, j, _ in pairs:
            assert i != j

    def test_no_duplicate_pairs(self):
        embeddings = np.random.randn(10, 5)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        pairs = build_candidate_pairs(embeddings, threshold=0.0)
        seen = set()
        for i, j, _ in pairs:
            assert (j, i) not in seen, f"Duplicate pair ({i},{j}) and ({j},{i})"
            seen.add((i, j))

    def test_similarity_scores_are_correct(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        pairs = build_candidate_pairs(embeddings, threshold=0.0)
        assert len(pairs) == 1
        assert abs(pairs[0][2]) < 0.01


class TestRunNliCausal:
    @patch("app.tasks.graph_tasks._get_nli_pipeline")
    def test_returns_scores_for_each_pair(self, mock_get_pipe):
        mock_pipe = MagicMock()
        mock_pipe.return_value = {
            "labels": ["entailment", "neutral", "contradiction"],
            "scores": [0.7, 0.2, 0.1],
        }
        mock_get_pipe.return_value = mock_pipe
        pairs = [("Fed raises rates", "Housing market slows")]
        results = run_nli_causal(pairs)
        assert len(results) == 1
        assert results[0]["entailment"] == 0.7
        assert results[0]["contradiction"] == 0.1

    @patch("app.tasks.graph_tasks._get_nli_pipeline")
    def test_empty_pairs_returns_empty(self, mock_get_pipe):
        results = run_nli_causal([])
        assert results == []
        mock_get_pipe.assert_not_called()
