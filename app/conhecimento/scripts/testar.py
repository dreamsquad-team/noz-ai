"""Testes manuais do agente de Conhecimento, sem escrever código.

O agente não guarda nada: cada consulta lê do MCP, calcula e responde. Uso (a partir de app/conhecimento):

    # responder a uma consulta (o que os outros agentes vão fazer)
    uv run python scripts/testar.py consultar --tipo usuario  --empresa emp-tintas --usuario u-emp-tintas-01 --simular-tema
    uv run python scripts/testar.py consultar --tipo empresa  --empresa emp-tintas --simular-tema
    uv run python scripts/testar.py consultar --tipo conteudo --empresa emp-tintas --conteudo c-emp-tintas-005 --simular-tema
    uv run python scripts/testar.py consultar --tipo grupo    --empresa emp-tintas --tag pintor --simular-tema

    # só ler do MCP mockado, pelo protocolo de verdade
    uv run python scripts/testar.py leitura --o-que eventos --empresa emp-tintas --usuario u-emp-tintas-01
    uv run python scripts/testar.py leitura --o-que conteudos --empresa emp-tintas --ids c-emp-tintas-001

    # só o tema (chama o Bedrock)
    uv run python scripts/testar.py tema --empresa emp-tintas -n 5

`--simular-tema` troca o Haiku por um tema de mentira (sem custo e sem AWS). Sem ele, a consulta chama o Bedrock
(Haiku 5.5): use AWS_PROFILE=noz (conta 862558960374).
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

CONTA_ESPERADA = "862558960374"
PADRAO_TEMA = ["c-emp-tintas-005", "c-emp-memorial-003", "c-emp-devhub-001"]


def cabecalho(texto: str) -> None:
    print(f"\n== {texto} ==")


def _data(valor):
    if not valor:
        return None
    dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _conferir_conta() -> bool:
    """Mostra em qual conta AWS a chamada vai rodar e avisa se não for a da NOZ."""
    try:
        import boto3

        ident = boto3.client("sts").get_caller_identity()
    except Exception as e:  # sem credencial, SSO expirado, etc.
        print(f"Sem credenciais AWS utilizáveis ({type(e).__name__}).")
        print("Rode:  aws sso login --profile <perfil>  e depois  export AWS_PROFILE=noz")
        return False
    conta = ident["Account"]
    print(f"Conta AWS: {conta} (perfil: {os.environ.get('AWS_PROFILE', 'padrão')})")
    if conta != CONTA_ESPERADA:
        print(f"ATENÇÃO: esperado {CONTA_ESPERADA}. Parando para não chamar o Bedrock na conta errada.")
        print("Use:  export AWS_PROFILE=noz")
        return False
    return True


# --- leitura ---

def cmd_leitura(args) -> int:
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client
    from strands.tools.mcp.mcp_client import MCPClient

    from tools.leitura import ErroLeitura, Leitor, chamador_do_cliente

    params = StdioServerParameters(command=sys.executable, args=["-m", "mock_mcp.server"], cwd=str(RAIZ))
    with MCPClient(lambda: stdio_client(params)) as cliente:
        leitor = Leitor(chamador_do_cliente(cliente))
        try:
            if args.o_que == "empresas":
                r = leitor.ler_empresas()
            else:
                if not args.empresa:
                    print("Erro: --empresa é obrigatório (exceto para 'empresas').")
                    return 2
                if args.o_que == "usuarios":
                    r = leitor.ler_usuarios(args.empresa, tag=args.tag)
                elif args.o_que == "conteudos":
                    r = leitor.ler_conteudos(args.empresa, ids=args.ids)
                else:
                    r = leitor.ler_eventos(args.empresa, desde=args.desde, ate=args.ate, id_usuario=args.usuario)
        except ErroLeitura as e:
            print(f"ErroLeitura: {e}")
            return 1

    cabecalho(f"{args.o_que}: {len(r.itens)} itens, {r.descartados} descartados")
    for item in r.itens[: args.mostrar]:
        print(item.model_dump_json())
    if len(r.itens) > args.mostrar:
        print(f"... (+{len(r.itens) - args.mostrar}; use --mostrar N para ver mais)")
    return 0


# --- tema ---

def _tema_simulado(system_prompt, entrada):
    """Tema sem modelo (sem custo): a palavra depois de 'sobre' no título dos dados do mock, em lote."""
    import re

    from tools.tema import ItemTema, SaidaTemaLote

    itens = []
    for bloco in entrada.split("### Conteúdo id=")[1:]:
        cid = bloco.split("\n", 1)[0]
        achou = re.search(r"sobre (\w+)", bloco)
        itens.append(ItemTema(id_conteudo=cid, topicos=[achou.group(1)] if achou else [], idioma="pt-BR"))
    return SaidaTemaLote(temas=itens)


def _conteudos(args):
    from agent.dominio import Conteudo
    from mock_mcp import dados

    if args.titulo or args.texto:
        return [
            Conteudo(
                id_conteudo="c-manual",
                id_empresa="emp-manual",
                tipo="post",
                titulo=args.titulo or "(sem título)",
                texto=args.texto,
                idioma="pt-BR",
                atualizado_em=datetime.now(timezone.utc),
            )
        ]
    if args.conteudo:
        ids = args.conteudo
    elif args.empresa:
        ids = [c["id_conteudo"] for c in dados.CONTEUDOS if c["id_empresa"] == args.empresa][: args.n]
    else:
        ids = PADRAO_TEMA
    por_id = {c["id_conteudo"]: c for c in dados.CONTEUDOS}
    faltando = [i for i in ids if i not in por_id]
    if faltando:
        print(f"Conteúdo(s) não encontrado(s) no mock: {', '.join(faltando)}")
        return None
    conteudos = [Conteudo.model_validate(por_id[i]) for i in ids]
    if len({c.id_empresa for c in conteudos}) > 1:  # o tema em lote é sempre de uma empresa só
        primeira = conteudos[0].id_empresa
        print(f"Os conteúdos são de empresas diferentes; usando só os de {primeira}.")
        conteudos = [c for c in conteudos if c.id_empresa == primeira]
    return conteudos


def cmd_tema(args) -> int:
    conteudos = _conteudos(args)
    if conteudos is None:
        return 2
    if not args.simular_tema and not _conferir_conta():
        return 1

    from tools.tema import extrair_temas, gerador_bedrock

    gerar = _tema_simulado if args.simular_tema else gerador_bedrock()
    inicio = time.monotonic()
    r = extrair_temas(conteudos, gerar)
    for c in conteudos:
        cabecalho(f"{c.id_conteudo} [{c.tipo}] {c.titulo}")
        print(f"texto: {(c.texto or '')[:140]!r}")
        t = r.temas.get(c.id_conteudo)
        if t is None:
            print("tema indisponível (falha do modelo)")
            continue
        print(f"topicos:   {t.topicos}")
        print(f"categoria: {t.categoria}")
        print(f"resumo:    {t.resumo}")
        print(f"idioma:    {t.idioma}")
    for aviso in r.avisos:
        print(f"aviso: {aviso}")
    print(f"\ntempo: {time.monotonic() - inicio:.1f}s")
    return 0


# --- consultar ---

def _montar_consulta(args):
    from agent.contract import ConsultaPerfilEmpresa, ConsultaPerfilGrupo, ConsultaPerfilUsuario, ConsultaTemaConteudo

    base = {"id_empresa": args.empresa, "modo": args.modo}
    janela = {"desde": _data(args.desde), "ate": _data(args.ate)}
    if args.tipo == "usuario":
        if not args.usuario:
            raise ValueError("--usuario é obrigatório para --tipo usuario")
        return ConsultaPerfilUsuario(**base, id_usuario=args.usuario, **janela)
    if args.tipo == "conteudo":
        if not args.conteudo:
            raise ValueError("--conteudo é obrigatório para --tipo conteudo")
        return ConsultaTemaConteudo(**base, id_conteudo=args.conteudo[0])
    if args.tipo == "grupo":
        if not args.tag:
            raise ValueError("--tag é obrigatório para --tipo grupo")
        return ConsultaPerfilGrupo(**base, tag=args.tag, **janela)
    return ConsultaPerfilEmpresa(**base)


def cmd_consultar(args) -> int:
    from pydantic import ValidationError

    from agent.consulta import ErroConsulta, responder
    from agent.fonte import ErroConfiguracao, abrir_leitor

    try:
        consulta = _montar_consulta(args)
    except (ValueError, ValidationError) as e:
        print(f"Consulta inválida: {e}")
        return 2
    if not args.simular_tema and not _conferir_conta():
        return 1

    if args.simular_tema:
        base = _tema_simulado
    else:
        from tools.tema import gerador_bedrock

        base = gerador_bedrock()
    chamadas_ao_modelo = []

    def gerar(system, entrada):
        chamadas_ao_modelo.append(entrada.count("### Conteúdo id="))
        return base(system, entrada)

    inicio = time.monotonic()
    try:
        with abrir_leitor(consulta.modo) as leitor:
            resposta = responder(consulta, leitor, gerar)
    except (ErroConfiguracao, ErroConsulta) as e:
        print(f"Erro: {e}")
        return 1
    tempo = time.monotonic() - inicio

    cabecalho(f"resposta ({consulta.tipo})")
    print(resposta.model_dump_json(indent=2, exclude_defaults=False))
    cabecalho("custo desta consulta")
    print(f"tempo: {tempo:.2f}s | chamadas ao modelo: {len(chamadas_ao_modelo)} | conteúdos analisados: {sum(chamadas_ao_modelo)}")
    print("Nada foi gravado.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Testes manuais do agente de Conhecimento")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("consultar", help="responde a uma consulta, como os outros agentes fariam (não grava nada)")
    c.add_argument("--tipo", choices=["usuario", "empresa", "conteudo", "grupo"], required=True)
    c.add_argument("--empresa", required=True, help="id_empresa, ex.: emp-tintas")
    c.add_argument("--usuario", help="id do usuário (--tipo usuario)")
    c.add_argument("--conteudo", action="append", help="id do conteúdo (--tipo conteudo)")
    c.add_argument("--tag", help="tag do grupo (--tipo grupo), ex.: pintor")
    c.add_argument("--desde", help="ISO 8601; vazio = janela padrão (90 dias)")
    c.add_argument("--ate", help="ISO 8601; vazio = agora")
    c.add_argument("--modo", choices=["mock", "real"], default="mock")
    c.add_argument("--simular-tema", action="store_true", help="tema sem chamar o Bedrock (sem custo, sem AWS)")
    c.set_defaults(func=cmd_consultar)

    l = sub.add_parser("leitura", help="lê do MCP mockado (pelo protocolo MCP, via stdio)")
    l.add_argument("--o-que", choices=["empresas", "usuarios", "conteudos", "eventos"], default="eventos")
    l.add_argument("--empresa", help="id_empresa, ex.: emp-tintas")
    l.add_argument("--usuario", help="eventos: só deste usuário")
    l.add_argument("--tag", help="usuarios: só os desta tag")
    l.add_argument("--ids", action="append", help="conteudos: só estes ids (repetível)")
    l.add_argument("--desde", help="ISO 8601 (eventos: início da janela)")
    l.add_argument("--ate", help="ISO 8601 (eventos: fim da janela)")
    l.add_argument("--mostrar", type=int, default=5, help="quantos itens imprimir (padrão 5)")
    l.set_defaults(func=cmd_leitura)

    t = sub.add_parser("tema", help="extrai o tema de conteúdos em lote (chama o Bedrock)")
    t.add_argument("--conteudo", action="append", help="id de conteúdo do mock (repetível)")
    t.add_argument("--empresa", help="usa os N primeiros conteúdos desta empresa")
    t.add_argument("-n", type=int, default=5, help="quantos conteúdos com --empresa (padrão 5)")
    t.add_argument("--titulo", help="conteúdo manual: título")
    t.add_argument("--texto", help="conteúdo manual: texto")
    t.add_argument("--simular-tema", action="store_true", help="tema de mentira, sem chamar o Bedrock")
    t.set_defaults(func=cmd_tema)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
