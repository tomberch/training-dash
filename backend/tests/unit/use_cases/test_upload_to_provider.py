"""Unit tests for UploadToProvider use case."""

import pytest

from trainingdash.use_cases.upload_to_provider import (
    ActivityNotFoundError,
    CredentialsNotFoundError,
    NoFitFileError,
    Provider,
    UploadToProvider,
)


class TestProvider:
    """Tests for Provider enum."""

    def test_provider_values(self):
        assert Provider.XERT.value == "xert"
        assert Provider.GARMIN.value == "garmin"

    def test_provider_from_string(self):
        assert Provider("xert") == Provider.XERT
        assert Provider("garmin") == Provider.GARMIN


class TestUploadToProviderExceptions:
    """Tests for UploadToProvider exception hierarchy."""

    def test_activity_not_found_error(self):
        err = ActivityNotFoundError("test-id")
        assert "test-id" in str(err)

    def test_no_fit_file_error(self):
        err = NoFitFileError("test-id")
        assert "test-id" in str(err)

    def test_credentials_not_found_error(self):
        err = CredentialsNotFoundError("xert")
        assert "xert" in str(err)


class TestUploadToProviderInit:
    """Tests for UploadToProvider initialization."""

    def test_requires_db_session(self):
        # Cannot instantiate without db
        with pytest.raises(TypeError):
            UploadToProvider()
