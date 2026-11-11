import contextvars
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreContext

import main
from config.log import FORMAT, SessionStamp


def _format(msg: str) -> str:
    record = logging.LogRecord("mcp_client.client", logging.WARNING, __file__, 1, msg, None, None)
    SessionStamp().filter(record)
    return logging.Formatter(FORMAT).format(record)


def test_inside_an_invocation_the_line_carries_the_session_id():
    """Um aviso de um logger de módulo — não do app.logger — sai amarrado à
    invocação que o causou."""

    def during_invocation():
        BedrockAgentCoreContext.set_request_context("req-1", "session-abc")
        return _format("gateway indisponível")

    line = contextvars.copy_context().run(during_invocation)

    assert "gateway indisponível" in line
    assert "[session-abc]" in line


def test_outside_an_invocation_the_stamp_is_a_dash():
    line = contextvars.Context().run(_format, "subindo")
    assert "[-]" in line


def test_main_installs_the_stamp_on_the_root_handler():
    assert main.app is not None  # main já importado: configure_logging rodou
    filters = [f for h in logging.getLogger().handlers for f in h.filters]
    assert any(isinstance(f, SessionStamp) for f in filters)
