"""Modelos de dados."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

__all__ = ["Transacao"]


@dataclass
class Transacao:
    """Um lançamento. ``valor`` negativo é saída (gasto); positivo é entrada."""

    data: date
    descricao: str
    valor: Decimal
    id: str = ""
    estabelecimento: str = ""
    categoria: str = "Outros"
    parcela: tuple[int, int] | None = None
    conta: str | None = None
    origem: str = ""
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def saida(self) -> bool:
        return self.valor < 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": self.data.isoformat(),
            "descricao": self.descricao,
            "estabelecimento": self.estabelecimento,
            "categoria": self.categoria,
            "valor": str(self.valor),
            "parcela": f"{self.parcela[0]}/{self.parcela[1]}" if self.parcela else "",
            "conta": self.conta or "",
            "id": self.id,
            "origem": self.origem,
        }
