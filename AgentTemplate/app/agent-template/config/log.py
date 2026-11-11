"""Logging do processo, com o session id da invocação em toda linha.

Sem isto, só o `app.logger` do BedrockAgentCore carimba o session id: os
`logging.getLogger(__name__)` do projeto — e os do Strands, como o WARNING do
`continue_on_error` quando o gateway cai — saem no CloudWatch sem como amarrar
a linha à invocação que a causou.
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreContext

FORMAT = "%(asctime)s %(levelname)s %(name)s [%(session_id)s] %(message)s"


class SessionStamp(logging.Filter):
    """Põe o session id da invocação em curso no registro, ou "-" fora dela.

    Fica no handler raiz, não num logger específico: assim qualquer logger que
    propaga sai carimbado.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = BedrockAgentCoreContext.get_session_id() or "-"
        return True


def configure_logging(level: str) -> None:
    """Handler raiz com o carimbo. Não usa basicConfig: ele não faz nada se o
    root já tiver um handler (a instrumentação OTel do runtime pode instalar
    um antes), e a linha sairia sem o session id."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(SessionStamp())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)
