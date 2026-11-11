import main


def test_agent_is_cached_per_session_and_user(monkeypatch):
    chamadas = []

    def fake_build(session_id, user_id, tools):
        chamadas.append((session_id, user_id))
        return object()

    monkeypatch.setattr(main, "build_agent", fake_build)
    get_agent = main.agent_factory()

    a1 = get_agent("s1", "u1")
    a2 = get_agent("s1", "u1")
    a3 = get_agent("s1", "u2")

    assert a1 is a2, "mesma sessão e usuário devem reusar o agente"
    assert a1 is not a3, "usuário diferente deve receber outro agente"
    assert chamadas == [("s1", "u1"), ("s1", "u2")]


def test_registered_tools_reach_the_factory(monkeypatch):
    vistas = {}

    def fake_build(session_id, user_id, tools):
        vistas["tools"] = tools
        return object()

    monkeypatch.setattr(main, "build_agent", fake_build)
    main.agent_factory()("s1", "u1")

    assert vistas["tools"] is main.tools


def test_placeholder_prompt_is_gone():
    """Guarda de regressão: o prompt genérico saiu do main.py de vez."""
    assert not hasattr(main, "DEFAULT_SYSTEM_PROMPT")


def test_the_gateway_client_joins_the_tools_when_available():
    """O MCPClient é um ToolProvider: entregá-lo em tools=[...] basta, o
    Agent cuida de abrir a sessão e listar as tools."""
    gateway = object()

    assert main.build_tools([main.add_numbers], gateway) == [main.add_numbers, gateway]


def test_without_a_gateway_the_tools_are_only_the_local_ones():
    """get_gateway_mcp_client() devolve None quando não há gateway utilizável;
    esse None não pode entrar na lista, ou o registry do Strands loga
    "unrecognized tool specification" a cada montagem de agente."""
    assert main.build_tools([main.add_numbers], None) == [main.add_numbers]
