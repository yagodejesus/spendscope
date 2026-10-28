"""Linha de comando: ``extrato arquivo.ofx``."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from . import __version__
from .extrato import Extrato
from .leitores import ExtratoInvalido


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="spendscope",
        description="Entenda seus extratos e faturas (OFX/CSV): categorias, assinaturas, parcelas e cobranças em dobro.",
    )
    p.add_argument("arquivos", nargs="+", help="arquivos .ofx ou .csv (de um ou vários bancos)")
    p.add_argument("--html", help="salva um relatório visual em HTML")
    p.add_argument("--csv", help="exporta as transações categorizadas em CSV")
    p.add_argument("--json", help="exporta as transações categorizadas em JSON")
    p.add_argument("--regras", help='JSON com suas regras: {"Academia": ["smart ?fit"]}')
    p.add_argument("--cartao", action="store_true", default=None, help="CSV de fatura com compras positivas")
    p.add_argument("--de", type=date.fromisoformat, help="data inicial (AAAA-MM-DD)")
    p.add_argument("--ate", type=date.fromisoformat, help="data final (AAAA-MM-DD)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = p.parse_args(argv)
    try:
        e = Extrato.ler(*a.arquivos, cartao=a.cartao, regras=a.regras)
    except (ExtratoInvalido, FileNotFoundError) as erro:
        print(f"extrato: {erro}", file=sys.stderr)
        return 1
    if a.de or a.ate:
        e = e.filtrar(a.de, a.ate)
    print(e.relatorio())
    for destino, metodo in ((a.html, e.relatorio_html), (a.csv, e.to_csv), (a.json, e.to_json)):
        if destino:
            metodo(destino)
            print(f"\n✓ salvo em {destino}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
