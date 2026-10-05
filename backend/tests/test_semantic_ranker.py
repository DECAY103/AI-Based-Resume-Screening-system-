import pytest

from app.evaluation import semantic_ranker


class FakeEmbeddingModel:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def encode(self, inputs, *, convert_to_numpy, show_progress_bar):
        assert convert_to_numpy is True
        assert show_progress_bar is False
        if isinstance(inputs, str):
            return self.embeddings[inputs]
        return [self.embeddings[value] for value in inputs]


def test_cosine_similarity_handles_identical_orthogonal_opposite_and_zero_vectors():
    assert semantic_ranker._cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert semantic_ranker._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert semantic_ranker._cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert semantic_ranker._cosine_similarity([0, 0], [1, 0]) == pytest.approx(0.0)


def test_rank_candidates_orders_descending_and_breaks_ties_by_candidate_id(monkeypatch):
    monkeypatch.setattr(
        semantic_ranker,
        "_model",
        FakeEmbeddingModel(
            {
                "rubric": [1, 0],
                "candidate-a": [1, 0],
                "candidate-b": [1, 0],
                "candidate-c": [0, 1],
            }
        ),
    )

    ranked = semantic_ranker.rank_candidates(
        "rubric",
        {"b": "candidate-b", "c": "candidate-c", "a": "candidate-a"},
        top_n=2,
        similarity_threshold=0.0,
    )

    assert [candidate.candidate_id for candidate in ranked] == ["a", "b", "c"]
    assert [candidate.promoted for candidate in ranked] == [True, True, False]
    assert [candidate.rank for candidate in ranked] == [1, 2, 3]
    assert [candidate.status for candidate in ranked] == ["scoring", "scoring", "pre_filtered"]


def test_rank_candidates_requires_top_n_and_threshold(monkeypatch):
    monkeypatch.setattr(
        semantic_ranker,
        "_model",
        FakeEmbeddingModel(
            {
                "rubric": [1, 0],
                "perfect": [1, 0],
                "partial": [3, 4],
            }
        ),
    )

    ranked = semantic_ranker.rank_candidates(
        "rubric",
        {"partial": "partial", "perfect": "perfect"},
        top_n=2,
        similarity_threshold=0.9,
    )

    assert [candidate.promoted for candidate in ranked] == [True, False]


def test_rank_candidates_can_promote_none_when_all_scores_are_below_threshold(monkeypatch):
    monkeypatch.setattr(
        semantic_ranker,
        "_model",
        FakeEmbeddingModel(
            {"rubric": [1, 0], "negative": [-1, 0], "orthogonal": [0, 1]}
        ),
    )

    ranked = semantic_ranker.rank_candidates(
        "rubric",
        {"negative": "negative", "orthogonal": "orthogonal"},
        top_n=2,
        similarity_threshold=0.1,
    )

    assert all(not candidate.promoted for candidate in ranked)
    assert ranked[-1].cosine_similarity_score == pytest.approx(-1.0)


def test_rank_candidates_rejects_invalid_ranker_configuration():
    with pytest.raises(ValueError, match="top_n"):
        semantic_ranker.rank_candidates("rubric", {}, top_n=-1, similarity_threshold=0.0)
    with pytest.raises(ValueError, match="similarity_threshold"):
        semantic_ranker.rank_candidates("rubric", {}, top_n=1, similarity_threshold=1.1)


def test_ranker_rejects_empty_candidate_inputs_and_nonfinite_vectors(monkeypatch):
    with pytest.raises(ValueError, match="candidate IDs"):
        semantic_ranker.rank_candidates("rubric", {" ": "resume"}, top_n=1, similarity_threshold=0)
    with pytest.raises(ValueError, match="must not be empty"):
        semantic_ranker.rank_candidates("rubric", {"candidate": "  "}, top_n=1, similarity_threshold=0)
    with pytest.raises(ValueError, match="finite"):
        semantic_ranker._cosine_similarity([float("nan")], [1.0])


def test_rank_candidates_uses_configured_top_n_when_not_explicitly_provided(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "stage1_top_n", 1)
    monkeypatch.setattr(
        semantic_ranker,
        "_model",
        FakeEmbeddingModel(
            {"rubric": [1, 0], "best": [1, 0], "second": [0, 1]}
        ),
    )

    ranked = semantic_ranker.rank_candidates(
        "rubric",
        {"best": "best", "second": "second"},
        similarity_threshold=0.0,
    )

    assert [candidate.promoted for candidate in ranked] == [True, False]
