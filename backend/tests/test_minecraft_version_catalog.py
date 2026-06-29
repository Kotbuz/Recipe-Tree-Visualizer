from app.services.minecraft_version_catalog import is_release_version, parse_catalog_markdown

SAMPLE_MARKDOWN = """
| Minecraft Version | Server Jar Download URL | Client Jar Download URL |
| 26.2 | <https://example.com/server.jar> | <https://example.com/client-26.2.jar> |
| 26.2-pre-1 | <https://example.com/pre-server.jar> | <https://example.com/pre-client.jar> |
| 1.21.4 | <https://example.com/server-1214.jar> | <https://example.com/client-1214.jar> |
"""

PLAIN_URL_MARKDOWN = """
| Minecraft Version    | Server Jar Download URL | Client Jar Download URL |
| 26.2                 | https://example.com/server.jar | https://example.com/client-26.2.jar |
| 26.2-pre-1           | https://example.com/pre-server.jar | https://example.com/pre-client.jar |
| 1.21.4               | https://example.com/server-1214.jar | https://example.com/client-1214.jar |
"""


def test_is_release_version_filters_prereleases() -> None:
    assert is_release_version("26.2")
    assert is_release_version("1.21.4")
    assert not is_release_version("26.2-pre-1")
    assert not is_release_version("1.21.4-rc-1")


def test_parse_catalog_markdown_extracts_client_urls() -> None:
    entries = parse_catalog_markdown(SAMPLE_MARKDOWN)

    assert [entry.version for entry in entries] == ["26.2", "1.21.4"]
    assert entries[0].client_url == "https://example.com/client-26.2.jar"
    assert entries[1].client_url == "https://example.com/client-1214.jar"


def test_parse_catalog_markdown_supports_plain_urls() -> None:
    entries = parse_catalog_markdown(PLAIN_URL_MARKDOWN)

    assert [entry.version for entry in entries] == ["26.2", "1.21.4"]
    assert entries[0].client_url == "https://example.com/client-26.2.jar"
    assert entries[1].client_url == "https://example.com/client-1214.jar"
