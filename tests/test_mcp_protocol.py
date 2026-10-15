"""Protocol dependency smoke test for the local MCP server."""

from pyflowmap.mcp_server import make_server


def test_mcp_server_constructs_with_sdk():
    server = make_server()
    assert server is not None
    assert callable(server.run)
