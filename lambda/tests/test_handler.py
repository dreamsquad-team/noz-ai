"""Provas do esqueleto da tool exposta pelo Gateway.

A regra que organiza o arquivo inteiro: `lambda_handler` NUNCA levanta. Uma
tool que estoura derruba a invocação do agente; uma tool que degrada devolve
lista vazia com motivo, e o modelo segue com o que tem. Todo teste abaixo é
uma forma de essa regra ser violada.
"""

import handler
import pytest


class FakeContext:
    """Dublê do context da Lambda. O Gateway entrega o nome da tool com o
    prefixo do target em client_context.custom."""

    def __init__(self, tool="noz-ai-target___tool_noz_ai"):
        self.client_context = type("CC", (), {"custom": {"bedrockAgentCoreToolName": tool}})()


def valid_event():
    return {"string_example": "um termo", "field_example": ["a", "b"], "client_id": 7}


# --- tool_name ---------------------------------------------------------------


def test_the_target_prefix_is_cut_from_the_tool_name():
    assert handler.tool_name(FakeContext()) == "tool_noz_ai"


def test_a_name_without_the_prefix_comes_back_whole():
    """Invocação direta, fora do Gateway: não há prefixo a cortar."""
    assert handler.tool_name(FakeContext("tool_noz_ai")) == "tool_noz_ai"


# --- o contrato de saída -----------------------------------------------------


def test_a_valid_call_returns_the_declared_output_shape():
    out = handler.lambda_handler(valid_event(), FakeContext())

    assert isinstance(out["example_fields"], list)
    assert isinstance(out["example_return"], int)


def test_a_successful_call_omits_motivo_vazio():
    """motivo_vazio é omitido no sucesso, não None: o outputSchema o declara
    como string, e null violaria o contrato que a tool anuncia ao modelo."""
    out = handler.lambda_handler(valid_event(), FakeContext())

    assert "motivo_vazio" not in out


# --- degradação: nada aqui pode levantar -------------------------------------


def test_an_unknown_tool_degrades_instead_of_raising():
    out = handler.lambda_handler(valid_event(), FakeContext("Outro___tool_que_nao_existe"))

    assert out["example_fields"] == []
    assert "motivo_vazio" in out


def test_a_malformed_context_does_not_raise():
    """Contexto sem client_context: cai no nome default em vez de estourar."""

    class Broken:
        pass

    out = handler.lambda_handler(valid_event(), Broken())

    assert isinstance(out["example_fields"], list)


def test_a_missing_required_string_degrades():
    out = handler.lambda_handler({"field_example": ["a"]}, FakeContext())

    assert out["example_fields"] == []
    assert "motivo_vazio" in out


def test_a_blank_required_string_degrades():
    out = handler.lambda_handler(
        {"string_example": "   ", "field_example": ["a"]}, FakeContext()
    )

    assert out["example_fields"] == []


def test_a_missing_required_array_degrades():
    out = handler.lambda_handler({"string_example": "x"}, FakeContext())

    assert out["example_fields"] == []


def test_a_non_iterable_array_degrades_as_a_value_error_not_a_type_error():
    """O modelo pode mandar um número onde o schema pede lista. iter(3) levanta
    TypeError; deixá-lo escapar cru do handler é o bug que este teste fixa."""
    out = handler.lambda_handler(
        {"string_example": "x", "field_example": 3}, FakeContext()
    )

    assert out["example_fields"] == []


def test_a_bare_string_array_is_accepted_as_one_item():
    """Modelos mandam "a" onde o schema pede ["a"] com frequência suficiente
    para valer o acolhimento — e sem ele a string viraria uma lista de
    caracteres."""
    out = handler.lambda_handler(
        {"string_example": "x", "field_example": "a"}, FakeContext()
    )

    assert out["example_return"] == 1


def test_a_body_that_blows_up_still_degrades(monkeypatch):
    """A última linha de defesa: se o corpo da tool levantar, o handler
    devolve o contrato degradado em vez de derrubar o agente."""

    def explode(args):
        raise RuntimeError("estourou")

    monkeypatch.setattr(handler, "run", explode)

    out = handler.lambda_handler(valid_event(), FakeContext())

    assert out["example_fields"] == []
    assert "motivo_vazio" in out


# --- _safe_log: nunca levanta, porque é o que observa o resto ----------------


def test_safe_log_truncates_a_long_value():
    assert len(handler._safe_log("x" * 10_000)) <= handler.SAFE_LOG_MAX_LEN


def test_safe_log_does_not_try_to_render_a_giant_int():
    """str(int) levanta ValueError acima de sys.get_int_max_str_digits()
    dígitos. bit_length() é O(1) e não converte nada."""
    assert "bits" in handler._safe_log(1 << 100_000)


def test_safe_log_survives_a_repr_that_raises():
    class Hostile:
        def __repr__(self):
            raise RuntimeError("repr hostil")

    assert handler._safe_log(Hostile())


@pytest.mark.parametrize("control", ["\n", "\r", "\t"])
def test_safe_log_strips_control_characters(control):
    """Um caractere de controle cru quebraria a linha no CloudWatch."""

    class Raw:
        def __repr__(self):
            return f"antes{control}depois"

    assert control not in handler._safe_log(Raw())
