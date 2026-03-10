import os
import tempfile

from app.services.ingestion.extractors.csv_extractor import extract_from_csv


def test_csv_extractor_basic():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        f.write("name,email,company\nAlice,alice@example.com,Acme\nBob,bob@example.com,Beta\n")
        path = f.name
    try:
        result = extract_from_csv(path)
        assert "Alice" in result
        assert "alice@example.com" in result
        assert "name" in result
    finally:
        os.unlink(path)


def test_csv_extractor_skips_empty_values():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        f.write("col1,col2\nfoo,\nbar,baz\n")
        path = f.name
    try:
        result = extract_from_csv(path)
        assert "foo" in result
        assert "baz" in result
    finally:
        os.unlink(path)


def test_csv_extractor_empty_csv_returns_empty_string():
    """CSV with only headers and no data rows should return empty string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        f.write("name,email,company\n")
        path = f.name
    try:
        result = extract_from_csv(path)
        assert result == ""
    finally:
        os.unlink(path)


def test_csv_extractor_preserves_falsy_string_values():
    """Values like '0' and 'False' must not be dropped."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        f.write("status,count\nFalse,0\n")
        path = f.name
    try:
        result = extract_from_csv(path)
        assert "False" in result
        assert "0" in result
    finally:
        os.unlink(path)


def test_csv_extractor_handles_bom():
    """File saved with UTF-8 BOM should parse correctly."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
        f.write(b"\xef\xbb\xbfname,email\nAlice,alice@example.com\n")
        path = f.name
    try:
        result = extract_from_csv(path)
        assert "Alice" in result
        assert "alice@example.com" in result
    finally:
        os.unlink(path)
