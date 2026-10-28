from datetime import date, timedelta
from decimal import Decimal

import spendscope as extrato
from spendscope import Extrato, limpar_estabelecimento


def t(d, desc, valor, id_=None):
    from spendscope.leitores import _nova

    tr = _nova(d, desc, Decimal(str(valor)), id_ or f"{d}{desc}{valor}", None, "teste")
    return tr


def test_limpeza_de_estabelecimentos():
    assert limpar_estabelecimento("PAG*NETFLIX.COM") == "Netflix"
    assert limpar_estabelecimento("COMPRA CARTAO DEBITO MP *ACAIDAMARIA 15/01") == "Acaidamaria"
    assert limpar_estabelecimento("PIX ENVIADO MARIA SOUZA") == "Maria Souza"
    assert limpar_estabelecimento("CLARO S.A.") == "Claro"


def test_categorias_padrao(ofx_exemplo):
    cats = {tr.estabelecimento: tr.categoria for tr in extrato.ler(ofx_exemplo)}
    assert cats["Netflix"] == "Assinaturas e streaming"
    assert cats["Supermercado Formosa"] == "Mercado"
    assert cats["Equatorial Para"] == "Casa e contas"
    assert cats["Smart Fit"] == "Academia e esportes"
    salarios = [tr for tr in extrato.ler(ofx_exemplo) if "SALARIO" in tr.descricao]
    assert salarios and all(tr.categoria == "Salário" for tr in salarios)


def test_regras_proprias_tem_prioridade(tmp_path, ofx_exemplo):
    regras = tmp_path / "regras.json"
    regras.write_text('{"Lazer com a família": ["acai"]}', encoding="utf-8")
    e = extrato.ler(ofx_exemplo, regras=regras)
    assert any(tr.categoria == "Lazer com a família" for tr in e)


def test_assinaturas_e_aumento_de_preco(ofx_exemplo):
    rec = {r.estabelecimento: r for r in extrato.ler(ofx_exemplo).recorrentes()}
    assert {"Netflix", "Spotify", "Smart Fit", "Claro", "Cosanpa", "Equatorial Para"} <= set(rec)
    n = rec["Netflix"]
    assert n.periodicidade == "mensal" and n.valor_atual == Decimal("59.90")
    assert round(n.aumento, 2) == 0.33 and n.custo_anual == Decimal("718.80")
    assert rec["Cosanpa"].aumento is None  # contas que oscilam não são "aumento"
    assert "Maria Souza" not in rec  # transferências não contam


def test_assinatura_com_duas_cobrancas_ja_aparece():
    base = date(2026, 1, 10)
    e = Extrato([t(base, "SPOTIFY", -21.9), t(base + timedelta(days=31), "SPOTIFY", -21.9)])
    assert [r.estabelecimento for r in e.recorrentes()] == ["Spotify"]


def test_gastos_irregulares_nao_sao_recorrentes():
    e = Extrato([t(date(2026, 1, d), "PADARIA", -10) for d in (1, 3, 4, 18, 25)])
    assert e.recorrentes() == []


def test_parcelamentos(ofx_exemplo):
    [p] = extrato.ler(ofx_exemplo).parcelamentos()
    assert (p.estabelecimento, p.parcela_atual, p.total_parcelas) == ("Magazine Luiza", 7, 10)
    assert p.compromisso == Decimal("569.70") and p.termina_em.year == 2026


def test_formatos_de_parcela():
    from spendscope.categorias import extrair_parcela

    assert extrair_parcela("LOJA X PARC 03/10") == (3, 10)
    assert extrair_parcela("Loja X - Parcela 2/6") == (2, 6)
    assert extrair_parcela("Loja X - 4/12") == (4, 12)
    assert extrair_parcela("COMPRA 15/01 LOJA") is None


def test_duplicadas(ofx_exemplo):
    pares = extrato.ler(ofx_exemplo).duplicadas()
    assert [(a.estabelecimento, a.valor) for a, _ in pares] == [("Uber Trip", Decimal("-27.40"))]


def test_resumos(ofx_exemplo):
    e = extrato.ler(ofx_exemplo)
    cats = e.por_categoria()
    assert sum(cats.values()) == e.saidas
    assert list(cats.values()) == sorted(cats.values(), reverse=True)
    assert len(e.por_mes()) == 6
    nome, total, vezes = e.maiores_estabelecimentos(1)[0]
    assert total > 0 and vezes >= 1


def test_filtrar(ofx_exemplo):
    e = extrato.ler(ofx_exemplo)
    julho = e.filtrar(date(2026, 7, 1), date(2026, 7, 31))
    assert julho and all(tr.data.month == 7 for tr in julho)
    assert all(tr.categoria == "Mercado" for tr in e.filtrar(categoria="Mercado"))
