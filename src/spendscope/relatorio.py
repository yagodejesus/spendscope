"""Relatórios em texto (terminal) e HTML (um arquivo, sem dependências, funciona offline)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
from typing import TYPE_CHECKING

from . import __version__

if TYPE_CHECKING:  # pragma: no cover
    from .extrato import Extrato

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def brl(v: Decimal | float, sinal: bool = False) -> str:
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefixo = ("−" if v < 0 else "+") if sinal and v != 0 else ("−" if v < 0 else "")
    return f"{prefixo}R$ {s}"


def _data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _mes(chave: str) -> str:
    ano, mes = chave.split("-")
    return f"{MESES[int(mes) - 1]}/{ano[2:]}"


def texto(e: Extrato) -> str:
    if not e.transacoes:
        return "Nenhuma transação encontrada."
    ini, fim = e.periodo
    linhas = [
        f"Extrato de {_data(ini)} a {_data(fim)} — {len(e)} transações",
        f"  Entradas {brl(e.entradas):>16}",
        f"  Saídas   {brl(e.saidas):>16}",
        f"  Saldo    {brl(e.entradas - e.saidas, True):>16}",
        "",
        "Gastos por categoria",
    ]
    cats = e.por_categoria()
    total = sum(cats.values()) or Decimal(1)
    for cat, v in cats.items():
        barra = "█" * max(1, round(24 * v / total))
        linhas.append(f"  {cat:<26} {brl(v):>14}  {barra} {v / total:.0%}")
    rec = e.recorrentes()
    if rec:
        linhas += ["", "Assinaturas e cobranças recorrentes"]
        for r in rec:
            alta = f"  ▲ {r.aumento:.0%} mais cara" if r.aumento else ""
            linhas.append(
                f"  {r.estabelecimento:<26} {brl(r.valor_atual):>12} {r.periodicidade:<10}"
                f" {brl(r.custo_anual):>14}/ano  próxima ~{_data(r.proxima)}{alta}"
            )
        linhas.append(f"  Total por ano: {brl(sum(r.custo_anual for r in rec))}")
    par = e.parcelamentos()
    if par:
        linhas += ["", "Parcelamentos em andamento"]
        for p in par:
            linhas.append(
                f"  {p.estabelecimento:<26} {p.parcela_atual:>2}/{p.total_parcelas:<2} de {brl(p.valor_parcela):>12}"
                f"  faltam {brl(p.compromisso)} (até {_mes(p.termina_em.strftime('%Y-%m'))})"
            )
        linhas.append(f"  Compromisso futuro: {brl(sum(p.compromisso for p in par))}")
    dup = e.duplicadas()
    if dup:
        linhas += ["", "Possíveis cobranças em dobro (confira!)"]
        for a, b in dup:
            linhas.append(f"  {a.estabelecimento:<26} {brl(a.valor):>12}  em {_data(a.data)} e {_data(b.data)}")
    return "\n".join(linhas)


_CSS = """
:root{--tinta:#12343b;--papel:#ffffff;--fundo:#eef3f1;--linha:#d5dfdb;--suave:#5b6f6b;--gasto:#d9483b;--ganho:#1f8a5b;--marca:#0f766e}
@media (prefers-color-scheme:dark){:root{--tinta:#e3ece9;--papel:#14201f;--fundo:#0c1514;--linha:#2a3a38;--suave:#93a8a3;--gasto:#ff7a6b;--ganho:#4cc38a;--marca:#2dd4bf}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--tinta);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 20px 48px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:20px}
h1{font-size:28px;margin:0;letter-spacing:-.02em}h2{font-size:17px;margin:0 0 14px}
.sub{color:var(--suave);font-size:14px}
.totais{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}
.total,.bloco{background:var(--papel);border:1px solid var(--linha);border-radius:14px;padding:18px 20px}
.total span{display:block;color:var(--suave);font-size:13px}.total strong{font-size:24px;font-variant-numeric:tabular-nums}
.bloco{margin-bottom:16px}.entrada{color:var(--ganho)}.saida{color:var(--gasto)}
.barra{display:grid;grid-template-columns:minmax(120px,210px) 1fr 112px;gap:12px;align-items:center;margin:8px 0;font-size:14px}
.barra strong{text-align:right;font-variant-numeric:tabular-nums}.trilho{height:10px;background:var(--fundo);border-radius:6px;overflow:hidden}.trilho i{display:block;height:100%;background:var(--marca);border-radius:6px}
.meses{display:flex;gap:14px;align-items:flex-end;height:170px;overflow-x:auto;padding-top:8px}
.mes{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:46px;font-size:12px;color:var(--suave)}
.colunas{display:flex;gap:3px;align-items:flex-end;height:130px}.colunas i{width:14px;border-radius:4px 4px 0 0}
.colunas .e{background:var(--ganho)}.colunas .s{background:var(--gasto)}
table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--suave);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--linha)}
td{padding:8px;border-bottom:1px solid var(--linha);font-variant-numeric:tabular-nums}tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right}.alta{color:var(--gasto);font-size:12px;font-weight:600}
.rodape{color:var(--suave);font-size:13px;margin-top:24px}.vazio{color:var(--suave)}
.rolagem{overflow-x:auto}
"""


def html(e: Extrato) -> str:
    if not e.transacoes:
        corpo = "<p class='vazio'>Nenhuma transação encontrada.</p>"
        return f"<!doctype html><meta charset='utf-8'><title>Extrato</title><style>{_CSS}</style><main>{corpo}</main>"
    ini, fim = e.periodo
    cats = e.por_categoria()
    maior = max(cats.values(), default=Decimal(1)) or Decimal(1)
    barras = "".join(
        f"<div class='barra'><span>{escape(c)}</span><div class='trilho'><i style='width:{float(v / maior) * 100:.1f}%'></i>"
        f"</div><strong>{brl(v)}</strong></div>"
        for c, v in cats.items()
    )
    meses = e.por_mes()
    topo = max((max(m["entradas"], m["saidas"]) for m in meses.values()), default=Decimal(1)) or Decimal(1)
    colunas = "".join(
        f"<div class='mes'><div class='colunas'>"
        f"<i class='e' title='Entradas {brl(m['entradas'])}' style='height:{float(m['entradas'] / topo) * 130:.0f}px'></i>"
        f"<i class='s' title='Saídas {brl(m['saidas'])}' style='height:{float(m['saidas'] / topo) * 130:.0f}px'></i>"
        f"</div>{_mes(k)}</div>"
        for k, m in meses.items()
    )
    rec = e.recorrentes()
    linhas_rec = "".join(
        f"<tr><td>{escape(r.estabelecimento)}</td><td>{r.periodicidade}</td><td class='n'>{brl(r.valor_atual)}</td>"
        f"<td class='n'>{brl(r.custo_anual)}</td><td>{_data(r.proxima)}</td>"
        f"<td>{f'<span class=alta>▲ {r.aumento:.0%}</span>' if r.aumento else ''}</td></tr>"
        for r in rec
    )
    bloco_rec = (
        f"<section class='bloco'><h2>Assinaturas e cobranças recorrentes — {brl(sum(r.custo_anual for r in rec))} por ano</h2>"
        "<div class='rolagem'><table><tr><th>Estabelecimento</th><th>Frequência</th><th class='n'>Valor</th>"
        f"<th class='n'>Por ano</th><th>Próxima</th><th>Preço</th></tr>{linhas_rec}</table></div></section>"
        if rec
        else ""
    )
    par = e.parcelamentos()
    bloco_par = (
        f"<section class='bloco'><h2>Parcelamentos — ainda faltam {brl(sum(p.compromisso for p in par))}</h2>"
        "<div class='rolagem'><table><tr><th>Compra</th><th>Parcela</th><th class='n'>Valor</th><th class='n'>Falta pagar</th>"
        "<th>Termina</th></tr>"
        + "".join(
            f"<tr><td>{escape(p.estabelecimento)}</td><td>{p.parcela_atual} de {p.total_parcelas}</td>"
            f"<td class='n'>{brl(p.valor_parcela)}</td><td class='n'>{brl(p.compromisso)}</td>"
            f"<td>{_mes(p.termina_em.strftime('%Y-%m'))}</td></tr>"
            for p in par
        )
        + "</table></div></section>"
        if par
        else ""
    )
    dup = e.duplicadas()
    bloco_dup = (
        "<section class='bloco'><h2>Possíveis cobranças em dobro</h2><p class='sub'>Mesmo estabelecimento e mesmo valor "
        "com até um dia de diferença. Confira com o banco.</p><table>"
        + "".join(
            f"<tr><td>{escape(a.estabelecimento)}</td><td class='n'>{brl(a.valor)}</td>"
            f"<td>{_data(a.data)} e {_data(b.data)}</td></tr>"
            for a, b in dup
        )
        + "</table></section>"
        if dup
        else ""
    )
    top = "".join(
        f"<tr><td>{escape(n)}</td><td class='n'>{q}×</td><td class='n'>{brl(v)}</td></tr>"
        for n, v, q in e.maiores_estabelecimentos(10)
    )
    saldo = e.entradas - e.saidas
    arquivos = escape(", ".join(e.arquivos))
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Extrato {_data(ini)} a {_data(fim)}</title><style>{_CSS}</style></head>
<body><main>
<header><h1>Seu dinheiro de {_data(ini)} a {_data(fim)}</h1><span class="sub">{len(e)} transações · {arquivos}</span></header>
<div class="totais">
<div class="total"><span>Entrou</span><strong class="entrada">{brl(e.entradas)}</strong></div>
<div class="total"><span>Saiu</span><strong class="saida">{brl(e.saidas)}</strong></div>
<div class="total"><span>Sobrou</span><strong class="{"entrada" if saldo >= 0 else "saida"}">{brl(saldo, True)}</strong></div>
</div>
<section class="bloco"><h2>Para onde foi o dinheiro</h2>{barras}</section>
<section class="bloco"><h2>Mês a mês</h2><div class="meses">{colunas}</div>
<p class="sub"><span class="entrada">■</span> entradas &nbsp; <span class="saida">■</span> saídas</p></section>
{bloco_rec}{bloco_par}{bloco_dup}
<section class="bloco"><h2>Onde você mais gasta</h2><div class="rolagem"><table>
<tr><th>Estabelecimento</th><th class="n">Vezes</th><th class="n">Total</th></tr>{top}</table></div></section>
<p class="rodape">Gerado pelo spendscope {__version__}. Seus dados não saíram do seu computador.</p>
</main></body></html>"""
