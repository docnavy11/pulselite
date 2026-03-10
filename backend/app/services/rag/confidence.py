from app.models.knowledge import Chunk


def compute_confidence(scored_chunks: list[tuple[Chunk, float]]) -> tuple[float, float]:
    if not scored_chunks:
        return 0.0, 0.0

    scores = [score for _, score in scored_chunks]
    confidence_score = max(scores)
    confidence_avg = sum(scores) / len(scores)
    return confidence_score, confidence_avg


def should_escalate(confidence_score: float, threshold: float) -> bool:
    return confidence_score < threshold
