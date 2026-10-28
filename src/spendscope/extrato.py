"""A classe :class:`Extrato`, que junta leitura, categorização e análises."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .analise import duplicadas, parcelamentos, por_categoria, por_mes, recorrentes
from .categorias import Categorizador
from .leitores import ler_arquivo
from .modelos import Transacao

__all__ = ["Extrato", "ler"]


class Extrato:
    """Um conjunto de transações (de um ou vários arquivos), já categorizadas."""

    def __init__(
        self,
        transacoes: Iterable[Transacao],
        categorizador: Categorizador | None = None,
        saldo: Decimal | None = None,
        arquivos: list[str] | None = None,
    ) -> None:
        vistos: set[tuple] = set()
        unicas = []
        for t in transacoes:
            k = (t.origem, t.id) if t.id else (t.origem, t.data, t.descricao, t.valor)
            if k not in vistos:
                vistos.add(k)
                unicas.append(t)
        self.transacoes = sorted(unicas, key=lambda t: (t.data, t.descricao))
        self.categorizador = categorizador or Categorizador()
        self.categorizador.aplicar(self.transacoes)
        self.saldo = saldo
        self.arquivos = arquivos or sorted({t.origem for t in self.transacoes if t.origem})

    # ------------------------------------------------------------------ construção
    @classmethod
    def ler(
        cls,
        *arquivos: str | Path,
        cartao: bool | None = None,
        regras: Mapping[str, Iterable[str]] | str | Path | None = None,
    ) -> Extrato:
        """Lê um ou mais arquivos OFX/CSV (podem ser de bancos e cartões diferentes)."""
        if isinstance(regras, (str, Path)):
            cat = Categorizador.de_arquivo(regras)
        else:
            cat = Categorizador(regras)
        todas: list[Transacao] = []
        saldo = None
        for a in arquivos:
            transacoes, info = ler_arquivo(a, cartao=cartao)
            todas.extend(transacoes)
            if len(arquivos) == 1:
                saldo = info.get("saldo")
        return cls(todas, cat, saldo, [Path(a).name for a in arquivos])

    def __add__(self, outro: Extrato) -> Extrato:
        return Extrato(self.transacoes + outro.transacoes, self.categorizador, None, self.arquivos + outro.arquivos)

    def __len__(self) -> int:
        return len(self.transacoes)

    def __iter__(self):
        return iter(self.transacoes)

    def __repr__(self) -> str:
        return f"<Extrato {len(self)} transações {self.periodo}>"

    # --------------------------------------------------------------------- filtros
    @property
    def periodo(self) -> tuple[date, date] | None:
        return (self.transacoes[0].data, self.transacoes[-1].data) if self.transacoes else None

    def filtrar(
        self, inicio: date | None = None, fim: date | None = None, categoria: str | None = None, texto: str | None = None
    ) -> Extrato:
        sel = [
            t
            for t in self.transacoes
            if (inicio is None or t.data >= inicio)
            and (fim is None or t.data <= fim)
            and (categoria is None or t.categoria == categoria)
            and (texto is None or texto.lower() in f"{t.descricao} {t.estabelecimento}".lower())
        ]
        novo = Extrato.__new__(Extrato)
        novo.transacoes, novo.categorizador, novo.saldo, novo.arquivos = sel, self.categorizador, None, self.arquivos
        return novo

    # -------------------------------------------------------------------- análises
    @property
    def entradas(self) -> Decimal:
        return sum((t.valor for t in self.transacoes if not t.saida), Decimal(0))

    @property
    def saidas(self) -> Decimal:
        return sum((-t.valor for t in self.transacoes if t.saida), Decimal(0))

    def por_categoria(self) -> dict[str, Decimal]:
        return por_categoria(self.transacoes)

    def por_mes(self) -> dict[str, dict[str, Decimal]]:
        return por_mes(self.transacoes)

    def maiores_estabelecimentos(self, n: int = 10) -> list[tuple[str, Decimal, int]]:
        tot: dict[str, list] = defaultdict(lambda: [Decimal(0), 0, ""])
        for t in self.transacoes:
            if t.saida:
                k = t.estabelecimento.lower()
                tot[k][0] += -t.valor
                tot[k][1] += 1
                tot[k][2] = t.estabelecimento
        ordem = sorted(tot.values(), key=lambda v: -v[0])[:n]
        return [(nome, total, qtd) for total, qtd, nome in ordem]

    def recorrentes(self, minimo: int = 3):
        return recorrentes(self.transacoes, minimo)

    def parcelamentos(self):
        return parcelamentos(self.transacoes)

    def duplicadas(self, janela_dias: int = 1):
        return duplicadas(self.transacoes, janela_dias)

    # ------------------------------------------------------------------- exportação
    def to_records(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self.transacoes]

    def to_csv(self, caminho: str | Path | None = None) -> str | None:
        buf = io.StringIO()
        campos = ["data", "descricao", "estabelecimento", "categoria", "valor", "parcela", "conta", "id", "origem"]
        w = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(self.to_records())
        if caminho is None:
            return buf.getvalue()
        Path(caminho).write_text(buf.getvalue(), encoding="utf-8")
        return None

    def to_json(self, caminho: str | Path | None = None) -> str | None:
        texto = json.dumps(self.to_records(), ensure_ascii=False, indent=2)
        if caminho is None:
            return texto
        Path(caminho).write_text(texto, encoding="utf-8")
        return None

    def to_dataframe(self):
        import pandas as pd

        df = pd.DataFrame(self.to_records())
        if not df.empty:
            df["data"] = pd.to_datetime(df["data"])
            df["valor"] = df["valor"].astype(float)
        return df

    def relatorio(self) -> str:
        from .relatorio import texto

        return texto(self)

    def relatorio_html(self, caminho: str | Path | None = None) -> str | None:
        from .relatorio import html

        conteudo = html(self)
        if caminho is None:
            return conteudo
        Path(caminho).write_text(conteudo, encoding="utf-8")
        return None


def ler(*arquivos: str | Path, cartao: bool | None = None, regras=None) -> Extrato:
    """Atalho para :meth:`Extrato.ler`."""
    return Extrato.ler(*arquivos, cartao=cartao, regras=regras)
