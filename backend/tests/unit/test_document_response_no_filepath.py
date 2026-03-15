from app.schemas.documents import DocumentResponse


def test_document_response_excludes_file_path():
    """file_path should be replaced with has_file boolean."""
    fields = DocumentResponse.model_fields
    assert "file_path" not in fields, "file_path leaks server paths to client"
    assert "has_file" in fields
