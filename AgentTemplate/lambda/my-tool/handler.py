"""Esqueleto da tool MCP exposta pelo AgentCore Gateway.

O nome da tool, o inputSchema e o outputSchema vivem em agentcore.json, em
`agentCoreGateways[].targets[].toolDefinitions[]`. Este arquivo implementa o
que aquele schema anuncia — se você mudar um, mude o outro, ou o modelo recebe
uma promessa que o código não cumpre.

A regra que organiza o arquivo: **lambda_handler nunca levanta**. Uma tool que
estoura derruba a invocação do agente; uma tool que degrada devolve o contrato
de saída vazio com um `motivo_vazio`, e o modelo segue com o que tem. Todo
`try` largo aqui é deliberado, e cada um loga antes de engolir — engolir em
silêncio esconderia um bug real no CloudWatch.

Para adaptar: troque TOOL e os campos em `validate_input`/`run`, e mantenha a
forma do retorno igual ao outputSchema.
"""

import logging

log = logging.getLogger()
log.setLevel(logging.INFO)

# O nome da tool, exatamente como declarado no toolDefinition.
TOOL = "tool_noz_ai"

# O Gateway prepõe "<NomeDoTarget>___" ao nome visível da tool.
DELIMITER = "___"

SAFE_LOG_MAX_LEN = 200

# str(int) levanta ValueError acima de sys.get_int_max_str_digits() dígitos
# (4300 por padrão, mínimo configurável 640). 256 bits (~77 dígitos) fica bem
# acima de qualquer id plausível e bem abaixo de qualquer configuração desse
# limite, então nunca chegamos perto da fronteira.
_MAX_INT_BITS_FOR_REPR = 256


def tool_name(context) -> str:
    """Corta o prefixo do target que o Gateway prepõe ao nome visível."""
    raw = context.client_context.custom["bedrockAgentCoreToolName"]
    if DELIMITER in raw:
        return raw.split(DELIMITER, 1)[1]
    return raw


def _safe_log(value) -> str:
    """Torna seguro qualquer valor vindo do modelo antes de entrar em log.

    Nunca levanta: é a última linha de defesa antes do CloudWatch, e uma falha
    aqui não pode derrubar a função que ela deveria observar.
    """
    try:
        if (
            isinstance(value, int)
            and not isinstance(value, bool)  # bool é int em Python
            and value.bit_length() > _MAX_INT_BITS_FOR_REPR
        ):
            # bit_length() é O(1) e não converte para string, ao contrário de
            # repr()/str() num int gigante.
            text = f"<int de ~{value.bit_length()} bits>"
        else:
            text = repr(value)
        # repr() já escapa caractere de controle (uma quebra de linha vira os
        # dois caracteres \ e n), então este filtro só dispara para um __repr__
        # de terceiro que devolva controle cru. O espaço é printable e passa;
        # \r e \t não são, e quebrariam a linha no CloudWatch igual a \n.
        text = "".join(c for c in text if c.isprintable())
        if len(text) > SAFE_LOG_MAX_LEN:
            text = text[: SAFE_LOG_MAX_LEN - 3] + "..."
        return text
    except Exception:
        return "<valor não representável em log>"


def _id(value) -> int:
    """-1 é o sentinela de ausente, para o id continuar sendo um inteiro."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return -1
    return n if n > 0 else -1


def _empty(reason: str) -> dict:
    """O contrato de saída quando não há o que devolver."""
    return {"example_fields": [], "example_return": 0, "motivo_vazio": reason}


def validate_input(event: dict) -> dict:
    """Traduz o que o modelo pediu no que `run` aceita.

    Levanta ValueError para entrada inválida; `lambda_handler` transforma isso
    em degradação. Validar aqui, e não dentro de `run`, mantém a fronteira
    clara: o que passa daqui já está no formato certo.
    """
    string_example = event.get("string_example")
    if not isinstance(string_example, str) or not string_example.strip():
        raise ValueError("string_example é obrigatório e precisa ser texto não vazio")

    field_example = event.get("field_example") or []
    if isinstance(field_example, str):
        # Modelos mandam "a" onde o schema pede ["a"] com frequência
        # suficiente para valer o acolhimento — e sem ele a string viraria uma
        # lista de caracteres.
        field_example = [field_example]
    else:
        try:
            iter(field_example)
        except TypeError:
            # Número ou booleano não é lista nem string (iter(True) também
            # falha, então não precisa de checagem de tipo à parte). Entrada de
            # tipo errado é ValueError, não TypeError vazando do handler.
            raise ValueError(
                f"field_example precisa ser uma lista de strings; recebeu "
                f"{_safe_log(field_example)}"
            ) from None
        field_example = [item for item in field_example if isinstance(item, str)]

    if not field_example:
        raise ValueError("field_example precisa conter ao menos uma string")

    return {
        "string_example": string_example.strip(),
        "field_example": field_example,
        "client_id": _id(event.get("client_id")),
    }


def run(args: dict) -> list[dict]:
    """O corpo da tool. É aqui que o seu projeto entra.

    Devolve a lista que vai em `example_fields`. Pode levantar à vontade:
    `lambda_handler` captura e degrada.
    """
    return [
        {
            "client_id": str(args["client_id"]),
            "example_field_return": item,
            "created_at": "",
            "score": 0,
        }
        for item in args["field_example"]
    ]


def lambda_handler(event, context):
    """Ponto de entrada. Nunca levanta."""
    try:
        tool = tool_name(context)
    except Exception as e:
        # Amplo de propósito: contexto malformado não pode derrubar o handler.
        # Mas engolir em silêncio esconderia um bug real de tool_name no
        # CloudWatch — loga antes de cair no default.
        log.warning("não deu para ler o nome da tool: %s", _safe_log(e))
        tool = TOOL  # invocação direta, fora do Gateway
    if tool != TOOL:
        return _empty(f"tool desconhecida: {_safe_log(tool)}")

    try:
        args = validate_input(event)
    except Exception as e:
        # validate_input documenta ValueError, mas um tipo que ninguém previu
        # não pode escapar por aqui. _safe_log nunca levanta, então montar a
        # mensagem não decide o caminho.
        message = _safe_log(e)
        log.warning("entrada rejeitada: %s", message)
        return _empty(f"entrada inválida: {message}")

    try:
        fields = run(args)
    except Exception as e:
        message = _safe_log(e)
        log.exception("a tool falhou: %s", message)
        return _empty(f"execução falhou: {message}")

    response = {"example_fields": fields, "example_return": len(fields)}
    if not fields:
        # Omitido no sucesso, não None: o outputSchema declara motivo_vazio
        # como string, e null violaria esse contrato.
        response["motivo_vazio"] = "a consulta não encontrou resultado"

    log.info(
        "execução ok: string_example=%s client_id=%s total=%s",
        _safe_log(args["string_example"]),
        args["client_id"],
        len(fields),
    )
    return response
