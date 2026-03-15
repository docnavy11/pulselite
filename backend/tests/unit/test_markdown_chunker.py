from app.services.ingestion.chunkers.markdown_chunker import chunk_markdown, MIN_TOKENS


class TestMarkdownChunkerMerging:
    """Small heading sections should be merged into larger chunks."""

    def test_tiny_sections_merged(self):
        """Multiple small sections should be grouped into one chunk."""
        md = "\n\n".join([
            "# Product",
            "We build quality tools.",
            "## Features",
            "Fast and reliable.",
            "## Pricing",
            "Starts at $10/mo.",
            "## Contact",
            "Email us at hello@example.com.",
        ])
        chunks = chunk_markdown(md)
        # All sections are tiny — should merge into 1 chunk
        assert len(chunks) == 1
        assert "Product" in chunks[0]["content"]
        assert "hello@example.com" in chunks[0]["content"]

    def test_large_section_not_merged(self):
        """A section with enough content stays as its own chunk."""
        long_body = "This is a detailed paragraph. " * 80  # ~400 tokens
        md = f"# Introduction\n\n{long_body}\n\n## Tiny\n\nJust a line."
        chunks = chunk_markdown(md)
        # Introduction is large enough, Tiny is small
        # They should NOT be merged together
        assert len(chunks) >= 2
        intro_chunk = next(c for c in chunks if "Introduction" in c["content"])
        assert intro_chunk["token_count"] >= MIN_TOKENS

    def test_heading_only_section_merged(self):
        """A heading with no body text should get merged with neighbors."""
        md = "# Title\n\n## Empty Section\n\n## Another\n\nSome content here."
        chunks = chunk_markdown(md)
        # Should merge these tiny sections
        assert len(chunks) == 1

    def test_preserves_first_heading_path(self):
        """Merged chunk keeps the heading_path of the first section."""
        md = "## Alpha\n\nSmall.\n\n## Beta\n\nAlso small."
        chunks = chunk_markdown(md)
        assert len(chunks) == 1
        assert "Alpha" in (chunks[0]["heading_path"] or "")

    def test_no_merge_when_sections_large_enough(self):
        """Sections above MIN_TOKENS stay separate."""
        body = "Detailed content here. " * 30  # ~90 tokens each
        md = f"## Section A\n\n{body}\n\n## Section B\n\n{body}"
        chunks = chunk_markdown(md)
        assert len(chunks) == 2

    def test_empty_content(self):
        assert chunk_markdown("") == []

    def test_no_headings_falls_through(self):
        """Text without headings won't use markdown chunker (tested at pipeline level)."""
        # But if called directly, it still works — treated as one section
        text = "Just plain text without any headings.\n\nAnother paragraph."
        chunks = chunk_markdown(text)
        assert len(chunks) == 1
