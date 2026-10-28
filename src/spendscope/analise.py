"""Análises: assinaturas e cobranças recorrentes, parcelamentos, possíveis duplicidades e resumos."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from .modelos import Transacao

__all__ = ["Recorrencia", "Parcelamento", "recorrentes", "parcelamentos", "duplicadas", "por_categoria", "por_mes"]

_PERIODOS = (
    ("semanal", 6, 8, 52),
    ("quinzenal", 13, 16, 26),
    ("mensal", 25, 35, 12),
    ("bimestral", 55, 66, 6),
    ("trimestral", 85, 95, 4),
    ("anual", 350, 380, 1),
)


@dataclass(frozen=True)
class Recorrencia:
    estabelecimento: str
    categoria: str
    periodicidade: str
    valor_atual: Decimal
    valor_medio: Decimal
    ocorrencias: int
    primeira: date
    ultima: date
    proxima: date
    custo_anual: Decimal
    aumento: float | None  # 0.10 = ficou 10% mais caro desde a primeira cobrança

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        for k in ("valor_atual", "valor_medio", "custo_anual"):
            d[k] = str(d[k])
        for k in ("primeira", "ultima", "proxima"):
            d[k] = d[k].isoformat()
        return d


@dataclass(frozen=True)
class Parcelamento:
    estabelecimento: str
    valor_parcela: Decimal
    parcela_atual: int
    total_parcelas: int
    restantes: int
    compromisso: Decimal  # quanto ainda falta pagar
    ultima_cobranca: date
    termina_em: date


def _chave(t: Transacao) -> str:
    return t.estabelecimento.lower().strip()


def recorrentes(transacoes: list[Transacao], minimo: int = 3) -> list[Recorrencia]:
    """Encontra cobranças que se repetem em intervalos regulares (assinaturas, mensalidades, contas)."""
    grupos: dict[str, list[Transacao]] = defaultdict(list)
    for t in transacoes:
        if t.saida and not t.parcela and t.categoria not in ("Transferências", "Saques"):
            grupos[_chave(t)].append(t)
    achados = []
    for itens in grupos.values():
        itens.sort(key=lambda t: t.data)
        # várias cobranças no mesmo dia contam como uma
        por_dia: dict[date, Transacao] = {}
        for t in itens:
            por_dia.setdefault(t.data, t)
        itens = list(por_dia.values())
        necessario = 2 if itens and itens[0].categoria == "Assinaturas e streaming" else minimo
        if len(itens) < necessario:
            continue
        intervalos = [(b.data - a.data).days for a, b in zip(itens, itens[1:])]
        mediana = median(intervalos)
        periodo = next((p for p in _PERIODOS if p[1] <= mediana <= p[2]), None)
        if not periodo:
            continue
        regulares = sum(1 for i in intervalos if abs(i - mediana) <= max(3, 0.25 * mediana))
        if regulares / len(intervalos) < 0.7:
            continue
        valores = [abs(t.valor) for t in itens]
        v_med = Decimal(median(valores))
        if any(abs(v - v_med) > v_med * Decimal("0.35") for v in valores):
            continue  # valores muito diferentes: provavelmente não é a mesma cobrança
        atual = valores[-1]
        # aumento de preço: valores que só sobem, em degraus (assinaturas), não contas que oscilam
        degraus = all(b >= a for a, b in zip(valores, valores[1:])) and len(set(valores)) <= 3
        subiu = valores[0] and atual > valores[0] * Decimal("1.03")
        aumento = float(atual / valores[0] - 1) if degraus and subiu else None
        achados.append(
            Recorrencia(
                estabelecimento=itens[-1].estabelecimento,
                categoria=itens[-1].categoria,
                periodicidade=periodo[0],
                valor_atual=atual,
                valor_medio=v_med.quantize(Decimal("0.01")),
                ocorrencias=len(itens),
                primeira=itens[0].data,
                ultima=itens[-1].data,
                proxima=itens[-1].data + timedelta(days=round(mediana)),
                custo_anual=(atual * periodo[3]).quantize(Decimal("0.01")),
                aumento=round(aumento, 4) if aumento else None,
            )
        )
    return sorted(achados, key=lambda r: -r.custo_anual)


def _somar_meses(d: date, meses: int) -> date:
    ano, mes = divmod(d.month - 1 + meses, 12)
    dia = min(d.day, 28)
    return date(d.year + ano, mes + 1, dia)


def parcelamentos(transacoes: list[Transacao]) -> list[Parcelamento]:
    """Compras parceladas em andamento e quanto ainda falta pagar."""
    ultimos: dict[tuple, Transacao] = {}
    for t in transacoes:
        if t.parcela and t.saida:
            k = (_chave(t), t.parcela[1], abs(t.valor))
            if k not in ultimos or t.parcela[0] > ultimos[k].parcela[0]:
                ultimos[k] = t
    res = []
    for t in ultimos.values():
        atual, total = t.parcela
        restantes = total - atual
        res.append(
            Parcelamento(
                estabelecimento=t.estabelecimento,
                valor_parcela=abs(t.valor),
                parcela_atual=atual,
                total_parcelas=total,
                restantes=restantes,
                compromisso=abs(t.valor) * restantes,
                ultima_cobranca=t.data,
                termina_em=_somar_meses(t.data, restantes),
            )
        )
    return sorted(res, key=lambda p: -p.compromisso)


def duplicadas(transacoes: list[Transacao], janela_dias: int = 1) -> list[tuple[Transacao, Transacao]]:
    """Pares de saídas com o mesmo estabelecimento e valor em até ``janela_dias`` — possíveis cobranças em dobro."""
    saidas = sorted((t for t in transacoes if t.saida and not t.parcela), key=lambda t: t.data)
    pares = []
    for i, a in enumerate(saidas):
        for b in saidas[i + 1 :]:
            if (b.data - a.data).days > janela_dias:
                break
            if a.id != b.id and a.valor == b.valor and _chave(a) == _chave(b) and a.categoria != "Transferências":
                pares.append((a, b))
    return pares


def por_categoria(transacoes: list[Transacao]) -> dict[str, Decimal]:
    totais: dict[str, Decimal] = defaultdict(Decimal)
    for t in transacoes:
        if t.saida:
            totais[t.categoria] += -t.valor
    return dict(sorted(totais.items(), key=lambda kv: -kv[1]))


def por_mes(transacoes: list[Transacao]) -> dict[str, dict[str, Decimal]]:
    meses: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"entradas": Decimal(0), "saidas": Decimal(0)})
    for t in transacoes:
        m = meses[t.data.strftime("%Y-%m")]
        if t.saida:
            m["saidas"] += -t.valor
        else:
            m["entradas"] += t.valor
    return dict(sorted(meses.items()))
