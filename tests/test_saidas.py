import json

import pytest

import spendscope as extrato
from spendscope.cli import main


def test_relatorio_texto(ofx_exemplo):
    r = extrato.ler(ofx_exemplo).relatorio()
    for trecho in ("Gastos por categoria", "Assinaturas", "Parcelamentos", "cobranças em dobro", "R$ 31.200,00"):
        assert trecho in r


def test_relatorio_html(ofx_exemplo, tmp_path):
    destino = tmp_path / "r.html"
    extrato.ler(ofx_exemplo).relatorio_html(destino)
    html = destino.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "Para onde foi o dinheiro" in html and "▲ 33%" in html


def test_exportacoes(ofx_exemplo, tmp_path):
    e = extrato.ler(ofx_exemplo)
    assert e.to_csv().splitlines()[0].startswith("data,descricao,estabelecimento,categoria,valor")
    dados = json.loads(e.to_json())
    assert len(dados) == 100 and dados[0]["valor"]


def test_dataframe(ofx_exemplo):
    pytest.importorskip("pandas")
    df = extrato.ler(ofx_exemplo).to_dataframe()
    assert len(df) == 100 and df["valor"].dtype == float


def test_cli(ofx_exemplo, tmp_path, capsys):
    html = tmp_path / "r.html"
    assert main([str(ofx_exemplo), "--html", str(html), "--de", "2026-05-01"]) == 0
    assert html.exists() and "Extrato de" in capsys.readouterr().out
    assert main([str(tmp_path / "nao_existe.ofx")]) == 1
