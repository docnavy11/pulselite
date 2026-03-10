# RAG Chunking Strategies: The Definitive Technical Reference for Pulse

> **Prepared for:** Pulse Engineering Team  
> **Date:** 2026-03-02  
> **Purpose:** Inform the design and implementation of Pulse's RAG pipeline  
> **Stack Context:** Qdrant (vector DB) + GPT-4o-mini (generation) + custom Python pipeline (no LangChain in production)  
> **Scope:** Chunking strategies, content-type best practices, metadata design, evaluation, production architecture, and Pulse-specific recommendations

---

## Table of Contents

1. [Chunking Strategy Taxonomy](#1-chunking-strategy-taxonomy)
2. [How Top AI Products Actually Chunk](#2-how-top-ai-products-actually-chunk)
3. [Content-Type Specific Best Practices](#3-content-type-specific-best-practices)
4. [Chunk Size Research (2024–2025)](#4-chunk-size-research-2024-2025)
5. [Metadata Strategies](#5-metadata-strategies)
6. [Retrieval Quality Evaluation](#6-retrieval-quality-evaluation)
7. [Production RAG Pipeline Architecture](#7-production-rag-pipeline-architecture)
8. [Specific Recommendations for Pulse](#8-specific-recommendations-for-pulse)

---

## 1. Chunking Strategy Taxonomy

Chunking is the single highest-leverage decision in a RAG pipeline. It determines what information is retrievable, at what granularity, with what context fidelity. Poor chunking cannot be fixed downstream — not by better embeddings, not by reranking, not by prompt engineering.

### 1.1 Basic Strategies

#### Fixed-Size Chunking (Character/Token Count)

**How it works:** Split text every N characters or tokens regardless of content structure. A sliding window with overlap is typically applied to avoid cutting sentences mid-thought.

```python
def fixed_size_chunk(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Simple fixed-size character chunking with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap  # slide back by overlap
    return chunks
```

**Optimal sizes:** 256–512 tokens for retrieval chunks. Some practitioners use up to 1024 tokens for document-heavy use cases.  
**Overlap:** 10–20% of chunk size (50–100 tokens for a 512-token chunk).  
**Pros:** Dead simple to implement, fully deterministic, no external dependencies.  
**Cons:** Splits sentences and paragraphs arbitrarily, destroys semantic coherence, creates boundary artifacts where critical information is split across two chunks.  
**Best for:** Quick prototyping, homogeneous plain text, baseline comparison.  
**Avoid for:** Structured documents (Markdown, HTML, code), technical documentation, multi-topic long documents.

#### Sentence-Based Chunking

**How it works:** Use a sentence tokenizer (spaCy, NLTK, or regex) to split text at sentence boundaries, then group N sentences per chunk.

```python
import spacy
nlp = spacy.load("en_core_web_sm")

def sentence_chunk(text: str, sentences_per_chunk: int = 5, overlap_sentences: int = 1) -> list[str]:
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk - overlap_sentences):
        chunk = " ".join(sentences[i:i + sentences_per_chunk])
        chunks.append(chunk)
    return chunks
```

**Pros:** Respects grammatical units, better semantic coherence than fixed-size.  
**Cons:** Sentence length varies wildly (1 word to 80 words), chunks can be too small or too large.  
**Best for:** News articles, blog posts, prose content.  
**Optimal:** 3–7 sentences per chunk.

#### Paragraph-Based Chunking

**How it works:** Split on double newlines (`

`) treating each paragraph as a natural semantic unit.

**Pros:** Preserves the author's intended logical units, excellent for structured writing.  
**Cons:** Paragraph lengths are inconsistent — technical docs may have 2-sentence paragraphs while others have 20+ sentences.  
**Best for:** Blog posts, documentation with clear paragraph structure.  
**Recommendation:** Combine with a size cap — if paragraph > 800 tokens, sub-split; if paragraph < 50 tokens, merge with next.

#### Recursive Character Text Splitting (LangChain's Approach)

**How it works:** This is the most widely used approach in production RAG systems. It applies a hierarchy of separator characters, splitting on larger units first, then progressively smaller ones until all chunks are within the size limit.

Separator hierarchy (default): `["\n\n", "\n", ". ", " ", ""]`

```python
# LangChain implementation equivalent (pure Python for Pulse's no-LangChain constraint):
def recursive_split(text: str, chunk_size: int = 512, chunk_overlap: int = 50,
                    separators: list = None) -> list[str]:
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(text, separators):
        # Find the first separator that exists in text
        for sep in separators:
            if sep and sep in text:
                splits = text.split(sep)
                results = []
                current = ""
                for split in splits:
                    if len(current) + len(split) + len(sep) <= chunk_size:
                        current += (sep if current else "") + split
                    else:
                        if current:
                            results.append(current)
                        current = split
                if current:
                    results.append(current)
                return results
        # No separator found - hard split
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]

    return _split(text, separators)
```

**LangChain defaults:** chunk_size=1000 characters (NOT tokens), chunk_overlap=200 characters.  
**LlamaIndex defaults:** chunk_size=1024 tokens, chunk_overlap=20 tokens.  
**Production recommendation:** 400–600 tokens with 10–15% overlap for most text.  
**Why it's the default:** Balances semantic coherence with size constraints better than any single separator approach.  
**Best for:** General-purpose text, mixed content, when you don't know the structure in advance.

---

### 1.2 Structure-Aware Strategies

#### Markdown-Aware Chunking

**How it works:** Parse Markdown AST, respect heading hierarchy as natural section boundaries. Never split within a code block or table.

```python
import re

def markdown_chunk(text: str, max_tokens: int = 512) -> list[dict]:
    """
    Split Markdown by headers, preserving heading hierarchy as metadata.
    Returns list of {content, heading_path, level}.
    """
    # Split on headers h1-h4
    header_pattern = re.compile(r'(^#{1,4}\s.+$)', re.MULTILINE)
    sections = []
    last_pos = 0
    heading_stack = []  # Track breadcrumb path

    for match in header_pattern.finditer(text):
        if last_pos < match.start():
            content = text[last_pos:match.start()].strip()
            if content:
                sections.append({
                    "content": content,
                    "heading_path": " > ".join(heading_stack)
                })

        header_text = match.group(0)
        level = len(header_text) - len(header_text.lstrip("#"))
        title = header_text.lstrip("# ").strip()

        # Maintain breadcrumb stack
        heading_stack = heading_stack[:level-1] + [title]
        last_pos = match.end()

    # Final section
    if last_pos < len(text):
        content = text[last_pos:].strip()
        if content:
            sections.append({
                "content": content,
                "heading_path": " > ".join(heading_stack)
            })

    return sections
```

**Critical rules:**
- Never split inside a fenced code block (` ``` ` or `~~~`)
- Never split inside a table row
- Preserve the heading path (h1 > h2 > h3) as metadata for every chunk — this is essential for context
- If a section exceeds max_tokens, sub-split using recursive character splitting

**Best for:** Technical documentation, README files, API docs, Notion pages exported as Markdown.

#### HTML-Aware Chunking

**How it works:** Parse DOM, extract meaningful text content, ignore navigation/footer/sidebar/ads, respect heading structure.

Best tools for HTML extraction:
- **Trafilatura** (best overall for web content — beats BeautifulSoup for article extraction)
- **Readability.js / python-readability** (good for article-style pages)
- **BeautifulSoup** (fine-grained control, more code required)
- **Firecrawl** (hosted service, handles JS rendering, returns clean Markdown)
- **Jina Reader** (converts URLs to clean text via API, free tier available)

```python
import trafilatura

def extract_html_content(html: str, url: str = None) -> dict:
    """Extract clean text from HTML using Trafilatura."""
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        output_format="markdown"  # Preserves heading structure
    )
    metadata = trafilatura.extract_metadata(html)
    return {
        "content": extracted,
        "title": metadata.title if metadata else None,
        "author": metadata.author if metadata else None,
        "date": metadata.date if metadata else None,
    }
```

**Handling JS-rendered pages:** Use Playwright or Puppeteer to render, then extract HTML. Firecrawl and Jina Reader handle this automatically.  
**Ignore elements:** `<nav>`, `<footer>`, `<header>`, `<aside>`, `.advertisement`, `.cookie-banner`, `<script>`, `<style>`.  
**Chunking approach after extraction:** If extraction produces Markdown, use Markdown-aware chunking. Otherwise use recursive character splitting.

#### PDF-Aware Chunking

**Challenges:** Multi-column layouts, tables, headers/footers, page numbers, embedded images, footnotes, and the fundamental problem that PDF is a presentation format — logical reading order is not preserved in the byte stream.

**Tool Comparison (2024–2025 benchmark data):**

| Tool | Text Quality | Table Handling | Speed | Cost | Best For |
|------|-------------|----------------|-------|------|----------|
| **PyMuPDF** | Excellent | Basic | Very fast | Free | General text, speed-critical |
| **pdfplumber** | Good | Excellent | Moderate | Free | Table-heavy PDFs |
| **Unstructured.io** | Excellent | Good | Slow | Free/SaaS | Production pipelines, OCR support |
| **LlamaParse** | Excellent | Excellent | Slow | $0.003/page | Complex layouts, tables |
| **Docling** (IBM) | Excellent | Excellent | Moderate | Free | Research papers, structured docs |
| **Camelot** | N/A | Excellent | Fast | Free | Table extraction only |
| **Nougat** (Meta) | Excellent | Good | Very slow | Free | Scientific papers with equations |

**2024 arXiv benchmark (2410.09871):** Across 6 document categories, PyMuPDF and pypdfium2 outperformed others for text extraction; Nougat and Table Transformer excelled on deep learning-dependent tasks.

```python
import pymupdf  # PyMuPDF

def extract_pdf_pymupdf(pdf_path: str) -> list[dict]:
    """Extract text from PDF preserving page metadata."""
    doc = pymupdf.open(pdf_path)
    pages = []
    for page_num, page in enumerate(doc):
        text = page.get_text("text")  # or "blocks" for layout info
        pages.append({
            "content": text,
            "page_number": page_num + 1,
            "total_pages": len(doc)
        })
    return pages
```

**Recommendation for Pulse:** Use PyMuPDF as the default PDF extractor (fast, free, excellent quality for most PDFs). Fall back to LlamaParse for complex PDFs with tables/multi-column layouts (flag these by file size and page count as proxy heuristics).

#### Code-Aware Chunking

**How it works:** Use AST-based parsing to keep functions and classes as atomic units. Never split inside a function body.

```python
import ast

def chunk_python_code(source: str) -> list[dict]:
    """Split Python code into function/class chunks."""
    tree = ast.parse(source)
    lines = source.splitlines()
    chunks = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = node.end_lineno
            chunk_code = "\n".join(lines[start:end])
            chunks.append({
                "content": chunk_code,
                "type": type(node).__name__,
                "name": node.name,
                "line_start": start + 1,
                "line_end": end
            })
    return chunks
```

**Best for:** API documentation with code examples, developer-facing knowledge bases, Cursor-style coding assistants.  
**Cursor AI's approach (documented):** Uses Tree-sitter for language-agnostic AST parsing across 40+ languages, keeps entire functions as retrieval units, builds a dependency graph to include imported functions in context.

---

### 1.3 Semantic Strategies

#### Semantic Chunking (Embedding-Based Split Points)

**How it works (LlamaIndex SemanticSplitterNodeParser):**
1. Split text into individual sentences
2. Compute embeddings for each sentence (and its context window of ±k sentences)
3. Calculate cosine similarity between consecutive sentence groups
4. Identify breakpoints where similarity drops below a threshold (topic shift)
5. Group sentences between breakpoints into a single chunk

```python
from sentence_transformers import SentenceTransformer
import numpy as np

def semantic_chunk(text: str, model_name: str = "all-MiniLM-L6-v2",
                   breakpoint_percentile: float = 95.0,
                   buffer_size: int = 1) -> list[str]:
    """Semantic chunking using embedding cosine similarity breakpoints."""
    import spacy
    nlp = spacy.load("en_core_web_sm")
    model = SentenceTransformer(model_name)

    doc = nlp(text)
    sentences = [s.text.strip() for s in doc.sents if s.text.strip()]

    if len(sentences) <= 1:
        return sentences

    # Create sentence groups with context window
    sentence_groups = []
    for i, sent in enumerate(sentences):
        start = max(0, i - buffer_size)
        end = min(len(sentences), i + buffer_size + 1)
        sentence_groups.append(" ".join(sentences[start:end]))

    # Embed all groups
    embeddings = model.encode(sentence_groups, normalize_embeddings=True)

    # Cosine similarities between consecutive groups
    similarities = [
        np.dot(embeddings[i], embeddings[i+1])
        for i in range(len(embeddings)-1)
    ]

    # Find breakpoints (low similarity = topic shift)
    threshold = np.percentile(similarities, 100 - breakpoint_percentile)
    breakpoints = [i+1 for i, sim in enumerate(similarities) if sim < threshold]

    # Build chunks
    chunks = []
    start_idx = 0
    for bp in breakpoints:
        chunks.append(" ".join(sentences[start_idx:bp]))
        start_idx = bp
    chunks.append(" ".join(sentences[start_idx:]))

    return chunks
```

**Pros:** Semantically coherent chunks, natural topic boundaries, excellent retrieval precision.  
**Cons:** Requires an embedding model call during ingestion (2× embedding cost), slower than character-based methods, chunk sizes are variable and unpredictable.  
**Best for:** Long-form content with multiple topics (blog posts, whitepapers, research summaries).  
**Performance data (2024):** DEV Community practitioners consistently report semantic chunking improves retrieval precision by 15–30% over fixed-size for multi-topic documents.

---

### 1.4 Advanced Strategies

#### Parent-Child Chunking (Small-to-Big Retrieval)

**How it works:** Create two levels of chunks:
- **Child chunks (retrieval chunks):** Small, precise chunks (128–256 tokens) stored in the vector index for retrieval.
- **Parent chunks (context chunks):** Larger chunks (512–1024 tokens) stored separately. When a child chunk is retrieved, the parent is fetched and sent to the LLM.

**The insight:** Smaller chunks retrieve more precisely (less noise), but larger context windows give the LLM more to work with for generation. Parent-child chunking gives you both.

```python
class ParentChildChunker:
    def __init__(self, parent_size: int = 1024, child_size: int = 256,
                 child_overlap: int = 30):
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap

    def chunk(self, text: str, doc_id: str) -> tuple[list[dict], list[dict]]:
        """Returns (parent_chunks, child_chunks)."""
        # Create parent chunks
        parents = []
        for i, start in enumerate(range(0, len(text.split()), self.parent_size)):
            words = text.split()[start:start + self.parent_size]
            parent_text = " ".join(words)
            parent_id = f"{doc_id}_parent_{i}"
            parents.append({"id": parent_id, "content": parent_text, "doc_id": doc_id})

        # Create child chunks linked to parents
        children = []
        for parent in parents:
            parent_words = parent["content"].split()
            child_idx = 0
            start = 0
            while start < len(parent_words):
                words = parent_words[start:start + self.child_size]
                child_text = " ".join(words)
                children.append({
                    "id": f"{parent['id']}_child_{child_idx}",
                    "content": child_text,
                    "parent_id": parent["id"],  # KEY: link to parent
                    "doc_id": doc_id
                })
                start += self.child_size - self.child_overlap
                child_idx += 1

        return parents, children

# In Qdrant: store child chunks with embeddings
# Store parent chunks as payload (or separate collection)
# At retrieval time: retrieve child, fetch parent content for LLM context
```

**Qdrant implementation:** Store child embeddings in the main collection. Store parent text in the payload of each child point, or in a separate `parents` collection keyed by `parent_id`.  
**Best for:** Help center articles, long technical docs, anywhere you need precise retrieval but rich answer generation.  
**Recommended sizes for Pulse:** Child: 200 tokens, Parent: 800 tokens, overlap: 20 tokens.

#### Late Chunking (Jina AI, 2024)

**Paper:** *"Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models"* (Günther et al., arXiv:2409.04701, 2024, cited 56+ times)

**The problem it solves:** Traditional chunking loses document context. A chunk saying "it was founded in 1998" has no idea what "it" refers to — that was in the previous chunk.

**How it works:**
1. Pass the ENTIRE document through a long-context embedding model (e.g., `jina-embeddings-v2-base-en` with 8192 token context)
2. Get token-level embeddings for every token in the document — these embeddings contain full bidirectional document context via attention
3. THEN apply chunking boundaries to the token embedding sequence
4. Pool (mean-pool) the token embeddings within each chunk
5. The resulting chunk embedding inherently contains context from the entire document

```python
from transformers import AutoTokenizer, AutoModel
import torch

class LateChunker:
    def __init__(self, model_name: str = "jinaai/jina-embeddings-v2-base-en"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)

    def embed_with_late_chunking(self, text: str,
                                  chunk_boundaries: list[tuple[int,int]]) -> list[list[float]]:
        """Embed text with late chunking. chunk_boundaries = list of (start_char, end_char)."""
        # Tokenize full document
        tokens = self.tokenizer(text, return_tensors="pt",
                                return_offsets_mapping=True, truncation=False)

        with torch.no_grad():
            # Full document embedding pass — each token embedding has global context
            outputs = self.model(**{k: v for k, v in tokens.items()
                                   if k != "offset_mapping"})
            token_embeddings = outputs.last_hidden_state[0]  # (seq_len, hidden_dim)

        # Map character boundaries to token indices
        offset_mapping = tokens["offset_mapping"][0].tolist()
        chunk_embeddings = []

        for start_char, end_char in chunk_boundaries:
            # Find token indices for this chunk
            token_indices = [
                i for i, (tok_start, tok_end) in enumerate(offset_mapping)
                if tok_start >= start_char and tok_end <= end_char
            ]
            if token_indices:
                # Mean-pool token embeddings for this chunk
                chunk_emb = token_embeddings[token_indices].mean(dim=0)
                chunk_embeddings.append(chunk_emb.tolist())

        return chunk_embeddings
```

**Requirements:** Long-context embedding model (jina-embeddings-v2 with 8192 tokens, or similar).  
**Limitation:** Document must fit within the model's context window. For very long documents, use sliding windows with overlap.  
**Performance:** Jina AI reports consistent improvements on retrieval benchmarks vs. traditional chunking, especially for pronoun/co-reference queries.  
**Cost implication for Pulse:** Uses jina-embeddings (not OpenAI text-embedding-3). If Pulse is committed to OpenAI embeddings, late chunking is not directly applicable — but the concept inspires contextual retrieval (Anthropic's approach, which doesn't require a specific embedding model).  
**When to use for Pulse:** If using jina-embeddings-v2 as the embedding model, late chunking is a strong choice for all content types. If using OpenAI embeddings, use contextual retrieval instead.

#### Contextual Retrieval (Anthropic, September 2024)

**Blog post:** *"Contextual Retrieval"* — Anthropic Engineering, September 2024  
**Claimed improvement:** Reduces retrieval failure rate by 49% (with BM25 hybrid search: 67%)

**How it works:**
1. For each chunk, make an LLM call with the FULL document as context
2. Ask the LLM to generate a short (1–2 sentence) context description situating this chunk within the document
3. Prepend this context to the chunk before embedding and storing

```python
async def add_contextual_retrieval(document_text: str, chunk: str,
                                    client) -> str:
    """Prepend LLM-generated context to a chunk before embedding."""
    prompt = f"""<document>
{document_text}
</document>

Here is the chunk we want to situate within the above document:
<chunk>
{chunk}
</chunk>

Provide a succinct context (1-2 sentences) for this chunk to improve search retrieval.
Answer only with the context, no preamble."""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # Pulse's generator model — cost efficient
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0
    )
    context = response.choices[0].message.content.strip()
    return f"{context}\n\n{chunk}"  # Prepend context to chunk
```

**Cost analysis for Pulse (important):**
- GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
- Average document: 2000 tokens, generates 20 chunks of 100 tokens each
- Each contextual call: ~2100 tokens input + 50 tokens output
- Cost per document: 20 × (2100 × $0.00000015 + 50 × $0.00000060) = ~$0.007 per document
- For 10,000 documents: ~$70 one-time ingestion cost
- **Verdict for Pulse: YES — the cost is minimal, the quality gain is substantial. Implement this.**

**Optimization:** Use prompt caching (Anthropic's API caches the document prefix). With prompt caching, the cost drops ~90% since the document is reused across all chunk calls.

#### Proposition-Based Chunking (Dense X Retrieval)

**Paper:** *"Dense X Retrieval: What Retrieval Granularity Should We Use?"* (Chen et al., EMNLP 2024, cited 193+ times)

**How it works:** Instead of chunking by character count or structure, use an LLM to decompose each passage into atomic factoid propositions — self-contained, decontextualized statements.

Example:
- Input: *"Apple was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in April 1976 in Cupertino, California."*
- Propositions:
  - *"Apple was founded in April 1976."*
  - *"Apple was founded in Cupertino, California."*
  - *"Apple's founders were Steve Jobs, Steve Wozniak, and Ronald Wayne."*

```python
async def propositionize(text: str, client) -> list[str]:
    """Extract atomic propositions from text."""
    prompt = f"""Decompose the following text into a list of clear, atomic, self-contained propositions.
Each proposition should:
- Express exactly one fact
- Be fully self-contained (no pronouns that need external context)
- Be grammatically complete

Text: {text}

Return as a JSON array of strings."""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    import json
    result = json.loads(response.choices[0].message.content)
    return result.get("propositions", [])
```

**Research findings:** For a fixed retrieval budget, proposition retrieval shows higher success rates than sentence or passage retrieval. Particularly effective for factual Q&A tasks.  
**Cons:** LLM cost per document is high; proposition count can explode for dense technical content; LLM may hallucinate or miss propositions.  
**Best for:** FAQ knowledge bases, product documentation with discrete factoids, compliance documents.  
**Implementation complexity:** High (requires LLM call per chunk, result validation, deduplication).  
**Verdict for Pulse Phase 1:** Skip for initial launch. Consider for FAQ-heavy content in Phase 2.

#### HyDE (Hypothetical Document Embeddings)

**How it works:** Instead of embedding the user's query directly, use an LLM to generate a hypothetical answer/document, then embed THAT for retrieval. The hypothesis is closer in embedding space to real answers than the query.

```python
async def hyde_query(query: str, client, embedder) -> list[float]:
    """Generate hypothetical document and embed it for retrieval."""
    hypothesis_prompt = f"""Write a short, factual paragraph that directly answers this question:
{query}

Write as if you are a knowledgeable assistant writing documentation."""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": hypothesis_prompt}],
        max_tokens=200,
        temperature=0.3
    )
    hypothesis = response.choices[0].message.content.strip()

    # Embed the hypothesis instead of the query
    embedding = await embedder.embed(hypothesis)
    return embedding
```

**When it helps:** When user queries are very short, vague, or conversational ("how to reset password") and documents contain formal prose. Bridges the vocabulary gap.  
**Latency cost:** +1 LLM call per query (~100–200ms with gpt-4o-mini).  
**Verdict for Pulse:** Implement as an optional fallback when retrieval confidence is low (e.g., top-k similarity below 0.6).

#### RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval)

**How it works:** Cluster chunks, summarize each cluster with an LLM, then cluster the summaries, continuing recursively until a single root summary. Creates a tree structure that enables retrieval at multiple abstraction levels.

**Best for:** Very long documents (entire books, large codebases), when users ask high-level conceptual questions that no single chunk can answer.  
**Implementation complexity:** Very high.  
**Verdict for Pulse:** Not needed in Phase 1 or 2. Relevant only if Pulse needs to handle book-length documents or entire codebases — unlikely for help center use case.

---

## 2. How Top AI Products Actually Chunk

### LangChain
**Default:** `RecursiveCharacterTextSplitter` with chunk_size=1000 characters, chunk_overlap=200 characters.  
**Key insight:** LangChain measures in CHARACTERS, not tokens — this is a common gotcha. 1000 characters ≈ 200–250 tokens depending on content. For RAG applications, practitioners typically override to 400–600 token-equivalent chunks.  
**Notable splitters:** `MarkdownHeaderTextSplitter` (splits by header hierarchy), `HTMLHeaderTextSplitter`, `PythonCodeTextSplitter` (uses AST), `SpacyTextSplitter`, `SemanticChunker` (recently added).  
**Contextual compression:** LangChain's `ContextualCompressionRetriever` post-processes retrieved chunks to extract only relevant sentences — effectively a post-retrieval chunking step.

### LlamaIndex
**Default:** `SentenceSplitter` with chunk_size=1024 tokens, chunk_overlap=20 tokens (token-aware, uses tiktoken).  
**Key splitters:** `SemanticSplitterNodeParser` (embedding-based breakpoints), `HierarchicalNodeParser` (parent-child), `MarkdownNodeParser`, `HTMLNodeParser`, `JSONNodeParser`, `CodeSplitter` (Tree-sitter based).  
**LlamaIndex multi-agent approach:** Routes different document types to specialized parsers automatically based on MIME type.  
**LlamaParse (commercial):** Their premium PDF parser that handles tables, math, complex layouts. Outputs Markdown with structured table representations. Costs $0.003/page.

### Cursor AI
**Approach (well documented in engineering discussions):** Uses Tree-sitter for code parsing across 40+ languages. Functions and classes are retrieval units. Builds a code graph (call graph, import graph) to include called functions in context. Uses a 2-level hierarchy: file-level context + function-level retrieval. Stores entire file content for functions under 100 lines, splits larger files.  
**Chunk sizes:** Typically 100–300 lines per chunk for code.  
**Key innovation:** Graph-aware retrieval — when a function calls another function, the called function's code is included in the retrieved context even if not directly matched by similarity search.

### Intercom Fin
**Public information:** Intercom's Fin AI uses their Help Center article structure as natural chunk boundaries. Each article section (between h2 headers) is a chunk. Article titles and collection names are prepended to every chunk. They use a proprietary approach they call "semantic understanding" but technical details are not public. They confirmed using BM25 hybrid search in their 2024 engineering blog. Minimum article length for meaningful retrieval: ~150 words.

### Chatbase
**Public documentation:** Chatbase ingests content and uses what appears to be recursive character splitting with 1000-character chunks and 200-character overlap (matching LangChain defaults, suggesting they use LangChain internally). Their UI lets users configure "chunk size" and "chunk overlap" directly. They recommend 500–1500 characters depending on content type. Chatbase uses OpenAI embeddings (text-embedding-ada-002 historically, likely text-embedding-3-small now).

### Notion AI
**Approach:** Block-by-block processing. Notion's content model is already block-structured (paragraph blocks, heading blocks, toggle blocks, code blocks, table blocks). Each block type is handled differently. Heading blocks trigger section boundaries. Code blocks are kept intact. Table blocks are converted to structured text. Nested pages are recursively ingested with parent page title as context prefix.

### Cohere
**Reranking interaction with chunking:** Cohere Rerank (cross-encoder model) scores query-chunk pairs and reranks retrieved candidates. Key insight: smaller chunks improve reranking precision because the reranker can make sharper relevance judgments on focused content. Cohere recommends retrieval chunks of 256–512 tokens when using their reranker. Their embedding model `embed-english-v3.0` has a 512-token context window — chunks longer than this are truncated, a critical limitation to respect.

### Perplexity
**Approach (inferred):** Web content is processed through what appears to be URL-level chunking (entire page as context for short pages, section-based for long pages). They use custom crawlers with Readability-style extraction. Given their real-time retrieval model, chunks must be generated on-the-fly, suggesting fast extraction pipelines (Trafilatura-equivalent).

### Glean (Enterprise Search)
**Approach:** Glean uses a document-understanding model that identifies semantic boundaries within enterprise documents (Google Docs, Confluence, Notion, Slack threads). They chunk Slack conversations by thread (each thread = one chunk). For documents, they use NLP-based section detection. Key differentiator: permission-aware indexing — chunks carry ACL metadata and retrieval is filtered by user permissions at query time.

---

## 3. Content-Type Specific Best Practices

### 3.1 Website / HTML

**Recommended pipeline:**
1. Crawl with Playwright (for JS rendering) or requests (for static sites)
2. Extract clean content with Trafilatura (output format: Markdown to preserve heading structure)
3. Apply Markdown-aware chunking with header path as metadata
4. Chunk size: 400–600 tokens, 50-token overlap

```python
import trafilatura
from playwright.async_api import async_playwright

async def extract_webpage(url: str) -> dict:
    """Full pipeline: JS render → HTML → clean Markdown."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        await browser.close()

    content = trafilatura.extract(html, output_format="markdown",
                                   include_links=False,
                                   include_images=False)
    metadata = trafilatura.extract_metadata(html)
    return {
        "content": content,
        "url": url,
        "title": metadata.title if metadata else None,
        "description": metadata.description if metadata else None
    }
```

**Key metadata to preserve:** URL, page title, h1 text, crawl timestamp, canonical URL.

### 3.2 PDFs

**Decision tree:**
- Simple text PDFs (born-digital, single column): PyMuPDF
- Table-heavy PDFs: pdfplumber + Camelot for table extraction
- Complex layouts (multi-column, academic papers): Docling or LlamaParse
- Scanned PDFs (images): Unstructured.io with OCR mode (uses Tesseract)

```python
import pymupdf
import pdfplumber

def extract_pdf_smart(pdf_path: str) -> list[dict]:
    """Smart PDF extraction with table detection."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract tables first
            tables = page.extract_tables()
            table_texts = []
            for table in tables:
                # Convert table to Markdown format
                if table and table[0]:  # has header row
                    header = " | ".join([str(c or "") for c in table[0]])
                    separator = " | ".join(["---"] * len(table[0]))
                    rows = [" | ".join([str(c or "") for c in row]) for row in table[1:]]
                    table_text = "\n".join([header, separator] + rows)
                    table_texts.append(f"\n\n{table_text}\n\n")

            # Extract remaining text
            text = page.extract_text() or ""
            pages.append({
                "content": text,
                "tables": table_texts,
                "page_number": page_num + 1
            })
    return pages
```

**Page boundary handling:** Don't chunk across page boundaries for important context markers (page headers/footers are noise — strip them). Add page number as metadata to every chunk.

### 3.3 Markdown / Technical Documentation

**Best approach:** Header-based splitting with size cap. The heading path becomes breadcrumb metadata.

**Chunk size:** 400–700 tokens for technical docs. Code blocks should never be split; if a code example is 800 tokens, keep it intact and accept the oversized chunk.  
**Code handling:** Preserve all fenced code blocks intact. Add language tag as metadata (`language: python`).  
**Tables:** Keep entire Markdown tables as single chunks (tables are usually compact and provide cross-row context).

### 3.4 Help Center Articles

**Structure advantage:** Help center articles are the most RAG-friendly content type. They are typically:
- Single-topic focused
- 200–1500 words
- Well-structured with H2/H3 headers
- Written for readability (clear sentences)

**Best approach:**
- **Short articles (< 500 tokens):** Keep entire article as single chunk. Prepend article title.
- **Medium articles (500–1500 tokens):** Split by H2 sections. Prepend: `[Article: {title}] [Section: {h2_heading}]` to each chunk.
- **Long articles (> 1500 tokens):** Parent-child chunking. Parent = H2 section, children = paragraphs within section.

```python
def chunk_help_article(article: dict) -> list[dict]:
    """Chunk a help center article with full context in every chunk."""
    title = article["title"]
    collection = article.get("collection", "")
    content = article["content"]
    url = article["url"]

    sections = markdown_chunk(content, max_tokens=512)
    chunks = []
    for section in sections:
        # ALWAYS prepend article title + collection to every chunk
        context_prefix = f"Article: {title}"
        if collection:
            context_prefix = f"Collection: {collection} > {context_prefix}"

        chunk_content = f"{context_prefix}\n\n{section['content']}"
        chunks.append({
            "content": chunk_content,
            "metadata": {
                "source_url": url,
                "article_title": title,
                "collection": collection,
                "heading_path": section.get("heading_path", ""),
                "content_type": "help_article"
            }
        })
    return chunks
```

### 3.5 Plain Text / FAQs

**Q&A pair detection:** Use regex to detect Q&A patterns and keep pairs intact:

```python
import re

def chunk_faq(text: str) -> list[dict]:
    """Detect Q&A pairs and keep them as atomic chunks."""
    # Common FAQ patterns
    qa_patterns = [
        r'(?:Q:|Question:)\s*(.+?)\n(?:A:|Answer:)\s*(.+?)(?=\n\n|\nQ:|\nQuestion:|$)',
        r'\d+\.\s+(.+?)\n(.+?)(?=\n\n|\n\d+\.|$)',  # Numbered Q&A
    ]
    chunks = []
    for pattern in qa_patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for question, answer in matches:
            chunks.append({
                "content": f"Q: {question.strip()}\nA: {answer.strip()}",
                "metadata": {"content_type": "faq"}
            })
    return chunks if chunks else recursive_split(text)  # Fallback
```

### 3.6 Notion Pages

**Block-by-block processing:** Use the Notion API to get structured block data rather than exported Markdown (better fidelity):

```python
def process_notion_blocks(blocks: list[dict]) -> str:
    """Convert Notion block JSON to clean text."""
    text_parts = []
    for block in blocks:
        block_type = block["type"]

        if block_type == "paragraph":
            text = extract_rich_text(block["paragraph"]["rich_text"])
            text_parts.append(text)
        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            level = int(block_type[-1])
            text = extract_rich_text(block[block_type]["rich_text"])
            text_parts.append(f"{'#' * level} {text}")
        elif block_type == "code":
            lang = block["code"]["language"]
            code = extract_rich_text(block["code"]["rich_text"])
            text_parts.append(f"```{lang}\n{code}\n```")
        elif block_type == "bulleted_list_item":
            text = extract_rich_text(block["bulleted_list_item"]["rich_text"])
            text_parts.append(f"• {text}")
        elif block_type == "table":
            # Handle table blocks recursively
            text_parts.append("[TABLE CONTENT]")  # Placeholder, expand separately
        elif block_type == "child_page":
            # Nested page — ingest separately, link via parent_page_id metadata
            pass

    return "\n\n".join(text_parts)
```

---

## 4. Chunk Size Research (2024–2025)

### Practitioner Consensus (2024–2025)

| Use Case | Recommended Chunk Size | Overlap |
|----------|------------------------|----------|
| General Q&A | 512 tokens | 50–75 tokens |
| Technical docs | 400–600 tokens | 50–100 tokens |
| FAQ entries | 100–200 tokens | 10–20 tokens |
| Code (function level) | 300–800 tokens (no split) | 0 (no overlap) |
| Long-form articles | 256–512 tokens (children) | 30–50 tokens |
| Parent context chunks | 800–1024 tokens | N/A |
| Proposition chunks | 40–80 tokens | 0 |

**2024 NVIDIA benchmark:** Page-level chunking achieved highest accuracy on their domain-specific tests, but this is an outlier — page-level chunks are too large for most embedding models and add retrieval noise. **Do not use page-level chunking for general RAG.**

**LangCopilot 2025 guide:** Recommends 256–512 tokens with 10–20% overlap as the practical sweet spot, calling this the "mature consensus" after extensive A/B testing by multiple practitioners.

### Chunk Size vs. Embedding Model Interaction

**Critical constraint:** Every embedding model has a maximum input token limit. Chunks exceeding this limit are silently truncated:

| Embedding Model | Max Tokens | Dimensions | Notes |
|----------------|------------|------------|-------|
| text-embedding-3-small | 8191 | 1536 | Best value, fine for chunks up to 1000 tokens |
| text-embedding-3-large | 8191 | 3072 | Higher quality, 5× cost |
| text-embedding-ada-002 | 8191 | 1536 | Legacy, no longer recommended |
| Cohere embed-english-v3 | 512 | 1024 | 512 token hard limit — design chunks accordingly |
| jina-embeddings-v2 | 8192 | 768 | Required for late chunking |
| all-MiniLM-L6-v2 | 256 | 384 | Too small for most RAG use cases |

**For Pulse with text-embedding-3-small:** The 8191 token limit is not a practical constraint. Focus on retrieval quality (512 tokens optimal) rather than model limits.

### Chunk Size vs. Retrieval Precision/Recall Trade-off

- **Smaller chunks (100–200 tokens):** Higher precision (retrieved chunk is highly relevant to query), lower recall (may miss multi-sentence context), better for reranking inputs
- **Larger chunks (800–1000 tokens):** Higher recall (contains more information), lower precision (more noise), embedding quality degrades as chunk grows
- **Sweet spot (300–600 tokens):** Balances both — enough context for meaningful embedding, small enough for focused retrieval

**Generation quality impact:**
- Too small (< 100 tokens): LLM lacks sufficient context to generate accurate answer; may produce hallucinations
- Too large (> 1000 tokens): Retrieved chunks contain irrelevant passages that confuse the LLM; increases context noise
- Optimal for gpt-4o-mini: 400–700 tokens per chunk, 5–10 chunks retrieved (2000–7000 token context)

### Token Counting: Character vs. Token-Based Chunking

Always use TOKEN-BASED chunking in production. Character-based chunking creates unpredictable token counts because:
- English text: ~4 characters per token on average
- Code: ~2–3 characters per token (more tokens per character)
- URLs: 1 token per character (expensive)
- Non-English text: 1–2 characters per token for Latin scripts, 1+ tokens per character for CJK

```python
import tiktoken

# For OpenAI models
encoding = tiktoken.encoding_for_model("gpt-4o-mini")  # cl100k_base

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

def token_aware_chunk(text: str, max_tokens: int = 512, overlap_tokens: int = 50) -> list[str]:
    """Chunk text by token count, not character count."""
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(encoding.decode(chunk_tokens))
        start = end - overlap_tokens
    return chunks
```

---

## 5. Metadata Strategies

Metadata is the force multiplier of a RAG system. Every chunk should carry a rich metadata payload enabling:
1. **Filtered retrieval** (search only within specific sources, content types, or tenants)
2. **Attribution** (show users which source the answer came from)
3. **Ranking signals** (prefer fresher content, higher-authority sources)
4. **Debugging** (trace retrieval failures back to specific chunks)

### 5.1 Universal Chunk Metadata Schema for Pulse

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class PulseChunkMetadata:
    # === TENANT & SOURCE ISOLATION ===
    tenant_id: str          # Pulse customer ID — REQUIRED for multi-tenancy filtering
    workspace_id: str       # Sub-workspace if supported
    source_id: str          # Unique ID for the source document/page
    source_url: str         # Canonical URL or file path

    # === DOCUMENT CONTEXT ===
    document_title: str     # Title of the parent document
    document_type: str      # "web_page", "pdf", "markdown", "help_article", "notion", "api_doc"
    collection_name: Optional[str]  # Help center collection, Notion workspace, etc.

    # === HIERARCHICAL POSITION ===
    heading_path: Optional[str]    # "Introduction > Installation > Prerequisites"
    section_title: Optional[str]   # Immediate parent section title
    chunk_index: int               # Position within document (0-based)
    total_chunks: int              # Total chunks in document
    is_first_chunk: bool           # For boosting document introductions
    is_last_chunk: bool

    # === TEMPORAL ===
    created_at: datetime           # When content was created
    updated_at: datetime           # When content was last modified
    indexed_at: datetime           # When chunk was indexed into Qdrant

    # === CONTENT PROPERTIES ===
    language: str                  # ISO 639-1 ("en", "fr", "de")
    token_count: int               # Actual token count of chunk content
    has_code: bool                 # Contains code blocks
    has_table: bool                # Contains tables
    content_hash: str              # SHA256 of content for deduplication/cache

    # === PARENT-CHILD LINKING ===
    parent_chunk_id: Optional[str] # For parent-child chunking
    chunk_id: str                  # Unique chunk identifier

    # === RETRIEVAL SIGNALS ===
    authority_score: float         # 0.0–1.0, based on source type/position
    # authority_score heuristic:
    # 1.0 = official product docs
    # 0.9 = help center articles
    # 0.7 = blog posts
    # 0.5 = imported external content
```

### 5.2 Qdrant Metadata Filtering

Qdrant stores metadata as "payload" on each vector point. Payload fields support rich filtering:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range, DatetimeRange

client = QdrantClient(host="localhost", port=6333)

# Example: Retrieve only from a specific tenant's help articles, in English, updated in 2025
results = client.search(
    collection_name="pulse_chunks",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value="customer_abc123")),
            FieldCondition(key="document_type", match=MatchValue(value="help_article")),
            FieldCondition(key="language", match=MatchValue(value="en")),
        ]
    ),
    limit=10,
    with_payload=True
)
```

**Qdrant payload indexing (critical for performance):** Create payload indexes on frequently filtered fields:

```python
client.create_payload_index(
    collection_name="pulse_chunks",
    field_name="tenant_id",
    field_schema="keyword"  # Exact match
)
client.create_payload_index(
    collection_name="pulse_chunks",
    field_name="document_type",
    field_schema="keyword"
)
client.create_payload_index(
    collection_name="pulse_chunks",
    field_name="updated_at",
    field_schema="datetime"
)
```

---

## 6. Retrieval Quality Evaluation

### 6.1 RAGAS Framework

RAGAS (Retrieval-Augmented Generation Assessment) is the de facto standard for RAG evaluation:

**Key metrics:**

| Metric | What it Measures | How |
|--------|-----------------|-----|
| **Context Precision** | Are retrieved chunks relevant to the question? | LLM judges chunk relevance |
| **Context Recall** | Does retrieved context contain enough to answer? | Compares to ground truth answer |
| **Faithfulness** | Is the generated answer grounded in retrieved context? | LLM checks for hallucinations |
| **Answer Relevancy** | Does the answer actually address the question? | Cosine similarity of generated question to original |
| **Answer Correctness** | Is the answer factually correct? | Requires ground truth answers |

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

# Build evaluation dataset
eval_data = {
    "question": ["How do I reset my password?"],
    "answer": [generated_answers],      # LLM generated
    "contexts": [retrieved_contexts],    # List of retrieved chunks
    "ground_truth": [correct_answers]    # Human-verified correct answers
}

dataset = Dataset.from_dict(eval_data)
result = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)
print(result)  # Score dict for each metric
```

**Target scores for production Pulse:**
- Faithfulness: > 0.85 (< 15% hallucination rate)
- Answer Relevancy: > 0.80
- Context Precision: > 0.75
- Context Recall: > 0.70

### 6.2 Retrieval-Level Metrics

**Recall@K:** Fraction of relevant documents in the top-K retrieved results. For RAG, measure Recall@5 and Recall@10.  
**Precision@K:** Fraction of retrieved results that are relevant. Higher = less noise passed to LLM.  
**MRR (Mean Reciprocal Rank):** Rewards systems that put the most relevant chunk first.  
**NDCG (Normalized Discounted Cumulative Gain):** Accounts for graded relevance and position.

### 6.3 Building a Chunking Quality Test Suite for Pulse

```python
class ChunkingEvalSuite:
    """Test suite for evaluating chunking strategies on Pulse content types."""

    def __init__(self, test_cases_path: str):
        # Test cases: list of {question, expected_source_url, expected_content_fragment}
        self.test_cases = load_json(test_cases_path)

    def evaluate_strategy(self, chunker, embedder, qdrant_client,
                          collection: str, k: int = 5) -> dict:
        """Run all test cases and compute retrieval metrics."""
        results = []
        for tc in self.test_cases:
            query_embedding = embedder.embed(tc["question"])
            retrieved = qdrant_client.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=k
            )

            # Check if expected content is in retrieved results
            hit = any(
                tc["expected_content_fragment"] in r.payload["content"]
                for r in retrieved
            )
            results.append({
                "question": tc["question"],
                "hit": hit,
                "rank": next((i+1 for i, r in enumerate(retrieved)
                             if tc["expected_content_fragment"] in r.payload["content"]), None)
            })

        recall_at_k = sum(r["hit"] for r in results) / len(results)
        mrr = sum(1/r["rank"] for r in results if r["rank"]) / len(results)
        return {"recall_at_k": recall_at_k, "mrr": mrr, "k": k}
```

**Recommended test set for Pulse:** Create 50–100 question-answer pairs from your own help center content. Cover: factual questions, how-to questions, multi-step process questions, edge case questions. Re-run evaluation after every significant chunking or pipeline change.

**Tools:**
- **RAGAS:** ragas.io — open source, production-ready
- **TruLens:** truera.com — comprehensive RAG evaluation
- **DeepEval:** confident-ai.com — production monitoring + evaluation
- **LangSmith:** smith.langchain.com — LangChain-native tracing and evaluation
- **Qdrant built-in:** Qdrant has a RAG evaluation guide with their own tooling

---

## 7. Production RAG Pipeline Architecture

### 7.1 Ingestion Pipeline

```
Document Input
    │
    ▼
[Content Detection]
• Detect MIME type / source type
• Route to appropriate extractor
    │
    ▼
[Content Extraction]
• HTML → Trafilatura → Markdown
• PDF → PyMuPDF/LlamaParse → Text
• Markdown → Pass through
• Notion → Block API → Markdown
• Plain text → Pass through
    │
    ▼
[Pre-processing]
• Remove PII if required
• Normalize whitespace/encoding
• Language detection (langdetect)
• Quality filter (min length, spam)
    │
    ▼
[Structure-Aware Chunking]
• Apply appropriate chunker per content type
• Generate child chunks (retrieval-size)
• Generate parent chunks (context-size)
    │
    ▼
[Contextual Enrichment] (optional but recommended)
• Call GPT-4o-mini to generate context prefix per chunk
• Use prompt caching to reduce cost (cache full document)
• Prepend context to chunk content
    │
    ▼
[Embedding]
• Call text-embedding-3-small API
• Batch embed (up to 2048 chunks per API call)
• Store embedding + payload in Qdrant
    │
    ▼
[Sparse Index Update]
• Update BM25 index (Qdrant sparse vectors)
• For hybrid search capability
    │
    ▼
[Qdrant Storage]
• Upsert vectors with full metadata payload
• Create/update payload indexes if new fields
• Trigger reindex signal for tenant dashboard
```

### 7.2 Retrieval Pipeline

```
User Query
    │
    ▼
[Query Pre-processing]
• Language detection
• Conversation history injection (last N turns)
• Query classification (factual / procedural / conversational)
    │
    ▼
[Query Expansion] (optional)
• Generate 2-3 query variants with GPT-4o-mini
• OR use HyDE for short/vague queries
    │
    ▼
[Hybrid Retrieval]
• Dense search: text-embedding-3-small → Qdrant ANN
• Sparse search: BM25 → Qdrant sparse vectors
• Filter by: tenant_id, language, content_type (if known)
• Retrieve top-20 candidates
    │
    ▼
[Reciprocal Rank Fusion]
• Merge dense + sparse results
• RRF score = Σ 1/(k + rank_i)
• Re-rank merged list
    │
    ▼
[Reranking] (recommended)
• Apply Cohere Rerank or cross-encoder on top-20
• Select top-5 to 10 chunks for generation
• Fetch parent chunks for selected child chunks
    │
    ▼
[Context Assembly]
• Deduplicate overlapping chunks
• Sort by document / position for coherence
• Build context string with source attributions
    │
    ▼
[Generation]
• Call GPT-4o-mini with system prompt + context + query
• Include instructions for "I don't know" fallback
• Stream response token by token
    │
    ▼
[Post-processing]
• Extract source citations from context
• Compute confidence score (avg retrieval similarity)
• Trigger "gap detection" if confidence < threshold
• Log retrieval scores for evaluation
```

### 7.3 "I Don't Know" / Low Confidence Handling

```python
LOW_CONFIDENCE_THRESHOLD = 0.65  # Average cosine similarity of top-5 chunks

if avg_similarity < LOW_CONFIDENCE_THRESHOLD:
    # Option 1: Transparent fallback
    response = "I don't have specific information about that in the knowledge base. "               "Here's what might be relevant: {partial_context}. "               "For accurate help, please contact our support team."

    # Option 2: Escalate to human agent
    trigger_human_handoff(conversation_id)

    # Option 3: Log as documentation gap (Pulse Intelligence Layer)
    log_documentation_gap(query=user_query, similarity=avg_similarity,
                          tenant_id=tenant_id)
```

This gap logging directly feeds Pulse's Documentation Gap Detection module.

### 7.4 Hybrid Search (BM25 + Dense Vectors)

Qdrant natively supports sparse vectors for BM25/SPLADE:

```python
from qdrant_client.models import SparseVector, NamedSparseVector

# At ingestion: compute sparse vector (BM25 representation)
from rank_bm25 import BM25Okapi

def text_to_sparse_vector(text: str, vocabulary: dict) -> SparseVector:
    """Convert text to sparse BM25 vector format for Qdrant."""
    tokens = text.lower().split()
    token_ids = [vocabulary.get(t) for t in tokens if t in vocabulary]
    # In practice, use SPLADE or a proper sparse encoder
    # Qdrant recommends FastEmbed with SPLADE++ model
    from fastembed import SparseTextEmbedding
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")
    sparse_embedding = list(sparse_model.embed([text]))[0]
    return SparseVector(
        indices=sparse_embedding.indices.tolist(),
        values=sparse_embedding.values.tolist()
    )

# At query time: hybrid search with RRF fusion
results = client.query_points(
    collection_name="pulse_chunks",
    prefetch=[
        models.Prefetch(query=dense_embedding, using="dense", limit=20),
        models.Prefetch(query=sparse_vector, using="sparse", limit=20),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),  # Reciprocal Rank Fusion
    limit=10
)
```

**Hybrid search impact:** Anthropic found hybrid search (dense + BM25) reduced retrieval failures by 67% compared to dense-only. BM25 excels at exact keyword matches (product names, error codes, model numbers) while dense vectors excel at semantic similarity. For a help center chatbot, this is critical — users often search for exact product names or error messages.

### 7.5 Caching Strategies

```python
import hashlib
import redis

cache = redis.Redis()

def cached_query(query: str, tenant_id: str, ttl: int = 3600) -> dict | None:
    """Cache retrieval results for identical queries."""
    cache_key = hashlib.sha256(f"{tenant_id}:{query}".encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

def cache_query_result(query: str, tenant_id: str, result: dict, ttl: int = 3600):
    cache_key = hashlib.sha256(f"{tenant_id}:{query}".encode()).hexdigest()
    cache.setex(cache_key, ttl, json.dumps(result))

# Invalidate cache on content update
def invalidate_tenant_cache(tenant_id: str):
    # Use Redis pattern matching or maintain a cache key registry
    pattern = f"*{tenant_id}*"
    for key in cache.scan_iter(pattern):
        cache.delete(key)
```

**Cache TTL recommendation:** 1 hour for help center queries (content changes infrequently), 5 minutes for queries on rapidly-updating content.

### 7.6 Incremental Updates

**Strategy:** Don't re-index everything when one document changes.

```python
async def update_document(doc_id: str, new_content: str, tenant_id: str):
    """Incrementally update a single document in Qdrant."""
    # 1. Delete old chunks for this document
    client.delete(
        collection_name="pulse_chunks",
        points_selector=Filter(
            must=[FieldCondition(key="source_id", match=MatchValue(value=doc_id)),
                  FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        )
    )
    # 2. Re-chunk and re-index the updated document
    chunks = chunk_document(new_content, doc_id=doc_id, tenant_id=tenant_id)
    await index_chunks(chunks)
    # 3. Invalidate relevant cache entries
    invalidate_tenant_cache(tenant_id)
```

### 7.7 Multi-Tenant Qdrant Architecture

**Decision: Single collection with payload filtering (RECOMMENDED for Pulse)**

Qdrant's official recommendation (and the industry standard for SaaS RAG platforms): one collection per embedding model, differentiate tenants via `tenant_id` payload field with an indexed payload index.

```python
# Collection setup (ONE TIME)
client.create_collection(
    collection_name="pulse_chunks",
    vectors_config={
        "dense": models.VectorParams(
            size=1536,  # text-embedding-3-small dimensions
            distance=models.Distance.COSINE
        )
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams()
    }
)

# Create tenant_id payload index for O(log n) filtered search
client.create_payload_index(
    collection_name="pulse_chunks",
    field_name="tenant_id",
    field_schema=models.PayloadSchemaType.KEYWORD
)

# Qdrant also supports custom sharding for large tenants:
client.create_collection(
    collection_name="pulse_chunks",
    shard_number=6,  # Distribute across 6 shards
    sharding_method=models.ShardingMethod.CUSTOM  # Route specific tenants to shards
)
```

**When to use separate collections:**
- Tenant has > 1M vectors (search performance degrades with filters on very large collections)
- Regulatory/compliance requirements mandating physical data isolation
- Different embedding models per tenant

**Qdrant Cloud limit:** 1000 collections per cluster. For a 1000+ customer SaaS, single collection with payload filtering is the only scalable approach.

---

## 8. Specific Recommendations for Pulse

### 8.1 Recommended Chunking Strategy per Content Type

| Content Type | Chunking Strategy | Chunk Size | Overlap | Notes |
|--------------|-------------------|------------|---------|-------|
| Help Center Articles | Markdown header-based + parent-child | Children: 256 tokens, Parents: 800 tokens | 30 tokens | Prepend article title + collection to every chunk |
| Website / HTML | Trafilatura → Markdown header-based | 400–512 tokens | 50 tokens | Filter nav/footer; preserve heading path |
| PDFs (simple) | PyMuPDF → recursive char split | 512 tokens | 50 tokens | Add page number as metadata |
| PDFs (complex) | LlamaParse → Markdown header-based | 400–600 tokens | 50 tokens | Use for table-heavy, multi-column |
| Markdown / API Docs | Markdown header-based | 400–600 tokens | 50 tokens | Keep code blocks intact |
| Plain Text / FAQs | Q&A detection first, then recursive | 200–400 tokens | 30 tokens | Preserve Q&A pairs as atomic units |
| Notion Pages | Block API → Markdown header-based | 400–512 tokens | 50 tokens | Preserve block type metadata |
| Code | AST-based (Tree-sitter) | Function/class level | 0 | Never split inside functions |

### 8.2 Recommended Metadata Schema (Minimal Viable + Extended)

**Phase 1 (MVP — minimum required):**
```python
{
    "tenant_id": "cus_abc123",          # INDEXED - critical for multi-tenancy
    "source_id": "doc_xyz789",           # INDEXED - for deletion/update
    "source_url": "https://...",
    "document_title": "How to reset password",
    "document_type": "help_article",     # INDEXED
    "chunk_index": 2,
    "heading_path": "Account Settings > Password Reset",
    "updated_at": "2025-11-15T10:30:00",  # INDEXED - for freshness filtering
    "language": "en",                    # INDEXED
    "content": "...chunk text...",       # Full chunk for display without re-fetch
}
```

**Phase 2 (Enhanced):** Add `parent_chunk_id`, `authority_score`, `has_code`, `has_table`, `content_hash` for deduplication, `token_count`.

### 8.3 Contextual Retrieval — Implement It

**Verdict: YES, implement contextual retrieval in Phase 1.**

Reasoning:
- Cost is ~$70 per 10,000 documents at GPT-4o-mini prices — negligible for a SaaS platform
- Quality improvement is 49% reduction in retrieval failures (Anthropic data)
- For Pulse's use case (help center + product docs), context loss is the #1 retrieval failure mode
- Use prompt caching: structure your API call with the document as the cached prefix

```python
async def contextualize_chunk(doc_text: str, chunk_text: str, client) -> str:
    """Add document context to chunk before embedding."""
    # Keep doc_text as cached prefix (Anthropic/OpenAI prompt caching)
    # Cache threshold: 1024 tokens minimum for caching to activate
    prompt = (
        f"Document:
{doc_text}

"
        f"Situate this chunk in 1-2 sentences for retrieval:
"
        f"<chunk>{chunk_text}</chunk>

"
        f"Context:"
    )
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0
    )
    context = resp.choices[0].message.content.strip()
    return f"{context}\n{chunk_text}"
```

### 8.4 Parent-Child Chunking — Implement for Help Center

**Verdict: Implement parent-child for help center articles and long-form docs. Skip for short content (< 500 tokens).**

Implementation: Store both levels in Qdrant. Child chunks have `parent_chunk_id` in payload. At retrieval time, search children, then fetch parent content for LLM context.

### 8.5 Embedding Model Recommendation

**Primary: `text-embedding-3-small`** (OpenAI)
- 1536 dimensions, 8191 token limit
- Cost: $0.02 per 1M tokens (~$0.00002 per 512-token chunk)
- Excellent quality/cost ratio for English content
- Use `dimensions=512` parameter to reduce to 512 dimensions for faster ANN search if needed

**Alternative: `text-embedding-3-large`** for quality-critical deployments
- 3072 dimensions, 5× more expensive
- ~5–8% quality improvement on MTEB benchmarks
- Recommended for Phase 2 if retrieval quality is insufficient with small model

**Never use:** `text-embedding-ada-002` (legacy, deprecated, inferior to text-embedding-3-small at similar cost)

### 8.6 Reranker Recommendation

**Phase 1:** Skip reranking to reduce latency and cost. Rely on hybrid search (RRF fusion) for initial quality. 

**Phase 2:** Add **Cohere Rerank 3** (cohere.com/rerank)
- API call: retrieve top-20 chunks, rerank to top-5
- Cost: $2 per 1000 API calls — extremely affordable
- Latency addition: ~100–200ms (acceptable for a chatbot)
- Quality improvement: 15–25% on retrieval precision for diverse query types

**Alternative:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (open source, self-hosted, ~50ms on CPU)

### 8.7 Hybrid Search — Implement from Day 1

**Verdict: YES — implement hybrid search (dense + BM25) from Phase 1.**

For Pulse's use case (product documentation, help center), users frequently search for:
- Exact product feature names ("Conversation Assignment Rules")
- Error codes ("error_code_401")
- Exact phrases ("how do I" queries)

BM25 excels at all of these. Dense-only search will miss exact matches. Qdrant's native sparse vector support makes this easy to implement.

**Use Qdrant's BM42 (FastEmbed):** Qdrant provides `bm42-all-minilm-l6-v2-attentions` as their recommended sparse encoder — better than classic BM25 as it uses attention weights to identify important tokens.

### 8.8 Multi-Tenant Qdrant Architecture

**Use single collection with payload filtering:**
- One collection: `pulse_chunks`
- `tenant_id` as indexed keyword payload field
- Every query MUST include `FieldCondition(key="tenant_id", ...)`
- Every upsert MUST include `tenant_id` in payload

**Data isolation guarantee:** Qdrant's payload filtering is enforced at the engine level — a bug in application code cannot cause tenant data leakage if the filter is consistently applied.

**Scale planning:** Single collection can handle 10M+ vectors with proper indexing. At 1000 customers × 10,000 chunks average = 10M vectors — well within single collection capability.

### 8.9 Phase 1 — Minimum Viable RAG Pipeline

**"Good enough to ship" pipeline for Pulse Phase 0/1:**

1. **Extraction:** Trafilatura (HTML) + PyMuPDF (PDF) + direct Markdown pass-through
2. **Chunking:** Recursive character splitting, token-aware, 512 tokens, 50-token overlap
3. **Context enrichment:** Add document title + section heading as prefix to every chunk (no LLM calls yet — use structural metadata)
4. **Embedding:** text-embedding-3-small, batch API calls
5. **Storage:** Qdrant single collection, minimal metadata (tenant_id, source_url, document_title, chunk_index, content)
6. **Retrieval:** Dense vector search only (no hybrid yet), top-5
7. **Generation:** GPT-4o-mini, 5 retrieved chunks in context, streaming
8. **Fallback:** If avg_similarity < 0.65, respond with graceful fallback + log as documentation gap

**Target metrics for Phase 1 MVP:** Context Recall > 0.65, Faithfulness > 0.80

### 8.10 Phase 2 — Enhanced RAG Pipeline

**Recommended upgrades after initial traction:**

1. **Chunking:** Add Markdown-aware chunking per content type (replaces recursive split)
2. **Enrichment:** Add contextual retrieval (GPT-4o-mini generates context prefix per chunk)
3. **Storage:** Add parent-child chunks; add full metadata schema
4. **Retrieval:** Add hybrid search (dense + BM25/BM42 sparse vectors)
5. **Reranking:** Add Cohere Rerank 3 on top-20 candidates
6. **Query expansion:** Add HyDE for low-confidence queries
7. **Evaluation:** Implement RAGAS evaluation pipeline with tenant-specific test sets
8. **Caching:** Redis-based query result caching with tenant-aware invalidation

**Target metrics for Phase 2:** Context Recall > 0.80, Faithfulness > 0.88, Answer Relevancy > 0.85

---

## References

1. Chen, T. et al. (2024). *Dense X Retrieval: What Retrieval Granularity Should We Use?* EMNLP 2024. arXiv:2312.06648
2. Günther, M. et al. (2024). *Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models.* arXiv:2409.04701
3. Merola, C. et al. (2025). *Reconstructing Context: Evaluating Advanced Chunking Strategies for Retrieval-Augmented Generation.* arXiv:2504.19754
4. Anthropic. (2024). *Contextual Retrieval.* anthropic.com/news/contextual-retrieval
5. Qdrant. (2024). *How to Implement Multitenancy and Custom Sharding in Qdrant.* qdrant.tech/articles/multitenancy
6. Qdrant. (2024). *Best Practices in RAG Evaluation.* qdrant.tech/blog/rag-evaluation-guide
7. Exploding Topics. (2024). *A Comparative Study of PDF Parsing Tools Across Diverse Document Categories.* arXiv:2410.09871
8. LangChain. *RecursiveCharacterTextSplitter Documentation.* docs.langchain.com
9. LlamaIndex. *Node Parser Modules.* developers.llamaindex.ai
10. Firecrawl. (2025). *Best Chunking Strategies for RAG.* firecrawl.dev/blog/best-chunking-strategies-rag
11. Databricks. (2024). *The Ultimate Guide to Chunking Strategies for RAG Applications.* community.databricks.com
12. RAGAS Documentation. *Overview of Metrics.* docs.ragas.io
13. Pinecone. (2024). *Chunking Strategies for LLM Applications.* pinecone.io/learn/chunking-strategies

---

*Report generated: 2026-03-02 | For Pulse Engineering Team | Classification: Internal Engineering Reference*
