from app.services.ingestion.chunkers.qa_chunker import chunk_qa


class TestQAChunkerGrouping:
    """QA chunker should group small pairs into ~512-token chunks."""

    def test_small_pairs_grouped_into_single_chunk(self):
        """Several short Q&A pairs should merge into one chunk."""
        text = "\n".join([
            "Q: What are your hours?",
            "A: 9am to 5pm, Monday through Friday.",
            "Q: Where are you located?",
            "A: 123 Main Street, Springfield.",
            "Q: What's your phone number?",
            "A: 555-1234.",
        ])
        chunks = chunk_qa(text)
        # 3 tiny pairs should fit in a single chunk
        assert len(chunks) == 1
        assert "What are your hours?" in chunks[0]["content"]
        assert "555-1234" in chunks[0]["content"]

    def test_large_pair_gets_own_chunk(self):
        """A single pair exceeding target tokens stays as its own chunk."""
        long_answer = "word " * 600  # ~600 tokens
        text = f"Q: Tell me everything\nA: {long_answer}"
        chunks = chunk_qa(text)
        assert len(chunks) == 1
        assert chunks[0]["token_count"] > 512

    def test_mixed_sizes_grouped_correctly(self):
        """Small pairs group together; a large pair forces a boundary."""
        small = "Q: Short?\nA: Yes.\n"
        large_answer = "word " * 500
        large = f"Q: Big question\nA: {large_answer}\n"

        text = small * 3 + large + small * 3
        chunks = chunk_qa(text)
        # Should have at least 3 chunks: small group, large, small group
        assert len(chunks) >= 3

    def test_empty_text_returns_empty(self):
        assert chunk_qa("") == []

    def test_single_pair_returns_one_chunk(self):
        text = "Q: Hello?\nA: Hi there!"
        chunks = chunk_qa(text)
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Q: Hello?\nA: Hi there!"

    def test_question_answer_format(self):
        """Also supports 'Question:/Answer:' format."""
        text = "Question: What is this?\nAnswer: A test.\nQuestion: Really?\nAnswer: Yes."
        chunks = chunk_qa(text)
        assert len(chunks) == 1
        assert "Q: What is this?" in chunks[0]["content"]
        assert "Q: Really?" in chunks[0]["content"]
