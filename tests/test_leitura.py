from datetime import date
from decimal import Decimal

import pytest

import spendscope as extrato
from spendscope.leitores import ler_csv, ler_ofx

OFX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<?OFX OFXHEADER="200" VERSION="220"?>
<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS><CURDEF>BRL</CURDEF>
<CCACCTFROM><ACCTID>5555xxxx1234</ACCTID></CCACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260105</DTPOSTED><TRNAMT>-39.90</TRNAMT><FITID>a1</FITID><NAME>NETFLIX.COM</NAME></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260107</DTPOSTED><TRNAMT>-120,50</TRNAMT><FITID>a2</FITID><MEMO>Farmácia São João</MEMO></STMTTRN>
</BANKTRANLIST></CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"""


def test_ofx_sgml_do_exemplo(ofx_exemplo):
    e = extrato.ler(ofx_exemplo)
    assert len(e) == 100
    assert e.saldo == Decimal("3120.55")
    assert e.transacoes[0].conta == "123456-7"
    assert e.entradas == Decimal("31200.00")


def test_ofx_xml_de_cartao_com_virgula():
    transacoes, info = ler_ofx(OFX_XML)
    assert info["cartao"] and info["conta"] == "5555xxxx1234"
    assert [t.valor for t in transacoes] == [Decimal("-39.90"), Decimal("-120.50")]
    assert transacoes[1].descricao == "Farmácia São João" and transacoes[1].data == date(2026, 1, 7)


def test_csv_de_conta_em_portugues():
    csv = "Data;Descrição;Valor\n05/01/2026;PIX RECEBIDO JOAO;1.500,00\n06/01/2026;SUPERMERCADO LIDER;-R$ 234,56\n"
    transacoes, _ = ler_csv(csv)
    assert [t.valor for t in transacoes] == [Decimal("1500.00"), Decimal("-234.56")]


def test_csv_de_fatura_com_compras_positivas_e_inversao_automatica():
    linhas = "\n".join(f"2026-01-{d:02d},Loja {d},{d * 10}.50" for d in range(1, 8))
    transacoes, info = ler_csv("date,title,amount\n" + linhas)
    assert info["cartao"] and all(t.valor < 0 for t in transacoes)


def test_csv_com_colunas_de_entrada_e_saida():
    csv = "Data,Histórico,Crédito,Débito\n01/02/2026,Salário,3000,\n02/02/2026,Aluguel,,1200\n"
    transacoes, _ = ler_csv(csv)
    assert [t.valor for t in transacoes] == [Decimal(3000), Decimal(-1200)]


def test_csv_sem_colunas_reconheciveis():
    with pytest.raises(extrato.ExtratoInvalido, match="colunas"):
        ler_csv("a,b\n1,2\n")


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("R$ -1.234,56", "-1234.56"),
        ("1234.56", "1234.56"),
        ("(12,00)", "-12.00"),
        ("1.234,56-", "-1234.56"),
        ("1,234.56", "1234.56"),
        ("+10", "10"),
    ],
)
def test_valor_br(texto, esperado):
    assert extrato.valor_br(texto) == Decimal(esperado)


def test_juntar_extratos_sem_duplicar(ofx_exemplo):
    e = extrato.ler(ofx_exemplo, ofx_exemplo)
    assert len(e) == 100
    assert len(extrato.ler(ofx_exemplo) + extrato.ler(ofx_exemplo)) == 100
