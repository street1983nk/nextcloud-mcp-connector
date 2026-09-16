"""The explicit Nextcloud target of the browser half (standalone OAuth, slice 2).

The login flow, the consent surface, the onboarding and the purge used to read the base URL
from the AppAPI deploy environment on every call. They now receive one validated
:class:`NextcloudTarget` from the composition root. These checks hold the value object and
the one ExApp resolver that builds it.
"""

import dataclasses

import pytest

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.exapp.target import exapp_target
from mcp_connector.nextcloud.target import NextcloudTarget

EXAPP_ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.1.0",
    config.ENV_NEXTCLOUD_URL: "https://cloud.test/nextcloud/",
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://nc.test", "http://nc.test"),
        ("  https://cloud.test/  ", "https://cloud.test"),
        ("https://cloud.test/nextcloud///", "https://cloud.test/nextcloud"),
        ("https://cloud.test:8443", "https://cloud.test:8443"),
    ],
)
def test_the_target_is_normalized_like_every_other_base_url(raw: str, expected: str) -> None:
    assert NextcloudTarget.from_url(raw).base_url == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "ftp://cloud.test", "cloud.test", "https://", "https://user:pw@cloud.test"],
    ids=["empty", "blank", "foreign scheme", "no scheme", "no host", "credentials"],
)
def test_an_unusable_address_is_refused_with_a_named_error(raw: str) -> None:
    with pytest.raises(ToolError):
        NextcloudTarget.from_url(raw)


@pytest.mark.parametrize("raw", ["http://nc.test/", " http://nc.test", "https://u:p@nc.test"])
def test_the_direct_constructor_accepts_only_a_normalized_value(raw: str) -> None:
    """No object of this type carries a value the normalization would have changed."""
    with pytest.raises((ValueError, ToolError)):
        NextcloudTarget(base_url=raw)


def test_the_netloc_is_host_and_port() -> None:
    assert NextcloudTarget.from_url("https://cloud.test:8443/nc").netloc == "cloud.test:8443"


def test_the_target_is_immutable() -> None:
    target = NextcloudTarget.from_url("http://nc.test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        target.base_url = "http://evil.example"  # type: ignore[misc]


def test_the_exapp_resolver_reads_the_deploy_environment_once() -> None:
    assert exapp_target(EXAPP_ENV) == NextcloudTarget.from_url("https://cloud.test/nextcloud")


def test_the_exapp_resolver_names_a_missing_nextcloud_url() -> None:
    env = {key: value for key, value in EXAPP_ENV.items() if key != config.ENV_NEXTCLOUD_URL}
    with pytest.raises(ToolError, match=config.ENV_NEXTCLOUD_URL):
        exapp_target(env)
