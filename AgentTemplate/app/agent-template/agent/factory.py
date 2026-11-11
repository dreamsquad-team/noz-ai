from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import (
    NullConversationManager,
)

from memory.session import get_memory_session_manager
from model.load import load_model
from prompts.load import load_prompt


def build_agent(session_id: str, user_id: str, tools: list) -> Agent:
    """Monta um Agent para o par (session_id, user_id).

    As tools vêm por parâmetro: quem decide o conjunto é o main.py, que é onde
    elas são registradas.
    """
    return Agent(
        model=load_model(),
        session_manager=get_memory_session_manager(session_id, user_id),
        conversation_manager=NullConversationManager(),
        system_prompt=load_prompt(),
        tools=tools,
        hooks=[],
    )
