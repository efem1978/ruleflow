from mcp_rules_assistant import __version__


def test_version_is_nonempty_string() -> None:
    assert isinstance(__version__, str) and len(__version__) > 0
