"""Strict ETag validation protects Range and If-Range request headers."""
import pytest

from meta_analyse.archive_resume import ResumeState, resume_headers, strong_etag


@pytest.mark.parametrize("etag", [
    'W/"weak"', '"contains space"', '"embedded"quote"',
    '"tab\tinside"', '"backslash\\inside"', '"newline\ninside"',
    '"carriage\rinside"', '""', "unquoted",
])
def test_reject_unsafe_or_weak_etag(etag):
    assert not strong_etag(etag)
    with pytest.raises(ValueError, match="strong ETag"):
        resume_headers(ResumeState(3, etag, 10))


def test_accept_strong_etag():
    assert strong_etag('"abc-123"')
    assert resume_headers(ResumeState(3, '"abc-123"', 10))["If-Range"] == '"abc-123"'
