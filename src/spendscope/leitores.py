"""Leitura de extratos OFX (versões 1.x SGML e 2.x XML) e CSV (exportações de bancos e cartões)."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .categorias import extrair_parcela, limpar_estabelecimento
from .modelos import Transacao

__all__ = ["ler_ofx", "ler_csv", "ler_arquivo", "valor_br", "ExtratoInvalido"]


class ExtratoInvalido(ValueError):
    """O arquivo não parece um extrato OFX ou CSV reconhecível."""


def _decodificar(bruto: bytes) -> str:
    cabecalho = bruto[:400].decode("ascii", "ignore").upper()
    if "CHARSET:1252" in cabecalho or "ENCODING:USASCII" in cabecalho and b"\xc3" not in bruto:
        try:
            return bruto.decode("cp1252")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return bruto.decode(enc)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", "replace")


def valor_br(texto: str) -> Decimal:
    """``"R$ -1.234,56"``, ``"1234.56"``, ``"(12,00)"``, ``"1.234,56-"`` → ``Decimal``."""
    s = texto.strip().replace("\u00a0", "").replace(" ", "")
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo, s = True, s[1:-1]
    s = re.sub(r"(?i)r\$|us\$|\$", "", s)
    if s.endswith("-"):
        negativo, s = not negativo, s[:-1]
    if s.startswith(("-", "−")):
        negativo, s = not negativo, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        v = Decimal(s)
    except InvalidOperation as exc:
        raise ExtratoInvalido(f"valor não reconhecido: {texto!r}") from exc
    return -v if negativo else v


def _data(texto: str) -> date:
    s = texto.strip()
    m = re.match(r"(\d{4})(\d{2})(\d{2})", s)  # OFX: 20260115120000[-3:BRT]
    if m and len(s) >= 8 and s[:8].isdigit():
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    raise ExtratoInvalido(f"data não reconhecida: {texto!r}")


def _nova(data: date, descricao: str, valor: Decimal, id_: str, conta: str | None, origem: str) -> Transacao:
    descricao = " ".join(descricao.split())
    if not id_:
        id_ = hashlib.sha1(f"{data}|{descricao}|{valor}".encode()).hexdigest()[:16]
    return Transacao(
        data=data,
        descricao=descricao,
        valor=valor,
        id=id_,
        estabelecimento=limpar_estabelecimento(descricao) or descricao,
        parcela=extrair_parcela(descricao),
        conta=conta,
        origem=origem,
    )


# ----------------------------------------------------------------------------- OFX
def ler_ofx(texto: str, origem: str = "") -> tuple[list[Transacao], dict]:
    inicio = texto.upper().find("<OFX>")
    if inicio < 0:
        raise ExtratoInvalido("não encontrei a tag <OFX>")
    corpo = texto[inicio:]

    def campo(nome: str, onde: str = corpo) -> str | None:
        m = re.search(rf"<{nome}>([^<\r\n]*)", onde, re.I)
        return m.group(1).strip() if m else None

    conta = campo("ACCTID")
    info = {
        "banco": campo("BANKID") or campo("ORG"),
        "conta": conta,
        "moeda": campo("CURDEF"),
        "cartao": "<CCSTMTRS>" in corpo.upper(),
        "saldo": None,
    }
    saldo = re.search(r"<LEDGERBAL>.*?<BALAMT>([^<\r\n]+)", corpo, re.I | re.S)
    if saldo:
        info["saldo"] = valor_br(saldo.group(1))

    transacoes = []
    blocos = re.findall(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>)", corpo, re.I | re.S)
    for bloco in blocos:
        campos = {m.group(1).upper(): m.group(2).strip() for m in re.finditer(r"<([A-Z0-9.]+)>([^<\r\n]*)", bloco, re.I)}
        if "TRNAMT" not in campos or "DTPOSTED" not in campos:
            continue
        nome, memo = campos.get("NAME", ""), campos.get("MEMO", "")
        descricao = memo if len(memo) > len(nome) else nome or memo
        t = _nova(_data(campos["DTPOSTED"]), descricao, valor_br(campos["TRNAMT"]), campos.get("FITID", ""), conta, origem)
        t.extra["tipo"] = campos.get("TRNTYPE", "")
        transacoes.append(t)
    return transacoes, info


# ----------------------------------------------------------------------------- CSV
def _chave(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9$]+", " ", s).split())


_COL_DATA = (
    "data",
    "date",
    "dt",
    "data lancamento",
    "data de lancamento",
    "data da compra",
    "data compra",
    "data movimento",
    "data da transacao",
    "data transacao",
)
_COL_DESC = (
    "descricao",
    "description",
    "title",
    "titulo",
    "historico",
    "lancamento",
    "estabelecimento",
    "detalhe",
    "detalhes",
    "memo",
    "nome",
    "transacao",
)
_COL_VALOR = ("valor", "amount", "valor r$", "valor $", "quantia", "valor brl", "valor rs", "montante")
_COL_ENTRADA = ("entrada", "entradas", "credito", "creditos", "receita")
_COL_SAIDA = ("saida", "saidas", "debito", "debitos", "despesa")
_COL_ID = ("id", "identificador", "fitid", "codigo")


def _achar(colunas: dict[str, str], opcoes: tuple[str, ...]) -> str | None:
    for o in opcoes:
        if o in colunas:
            return colunas[o]
    for o in opcoes:
        for k, original in colunas.items():
            if k.startswith(o + " "):
                return original
    return None


def ler_csv(texto: str, origem: str = "", cartao: bool | None = None) -> tuple[list[Transacao], dict]:
    """``cartao=True`` inverte o sinal (faturas que trazem compras como valores positivos).
    ``None`` decide sozinho: se quase todos os valores forem positivos, trata como fatura de cartão."""
    amostra = texto[:5000]
    try:
        delimitador = csv.Sniffer().sniff(amostra, delimiters=",;\t|").delimiter
    except csv.Error:
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    if not leitor.fieldnames:
        raise ExtratoInvalido("CSV vazio")
    colunas = {_chave(c): c for c in leitor.fieldnames if c}
    c_data, c_desc = _achar(colunas, _COL_DATA), _achar(colunas, _COL_DESC)
    c_valor, c_ent, c_sai = _achar(colunas, _COL_VALOR), _achar(colunas, _COL_ENTRADA), _achar(colunas, _COL_SAIDA)
    c_id = _achar(colunas, _COL_ID)
    if not c_data or not c_desc or not (c_valor or c_ent or c_sai):
        raise ExtratoInvalido(f"não reconheci as colunas de data, descrição e valor em: {list(leitor.fieldnames)}")

    transacoes = []
    for linha in leitor:
        if not (linha.get(c_data) or "").strip():
            continue
        if c_valor and (linha.get(c_valor) or "").strip():
            valor = valor_br(linha[c_valor])
        else:
            entrada = valor_br(linha[c_ent]) if c_ent and (linha.get(c_ent) or "").strip() else Decimal(0)
            saida = valor_br(linha[c_sai]) if c_sai and (linha.get(c_sai) or "").strip() else Decimal(0)
            valor = abs(entrada) - abs(saida)
        transacoes.append(
            _nova(
                _data(linha[c_data]), linha.get(c_desc) or "", valor, (linha.get(c_id) or "") if c_id else "", None, origem
            )
        )

    positivos = sum(1 for t in transacoes if t.valor > 0)
    inverter = cartao if cartao is not None else (len(transacoes) >= 5 and positivos / len(transacoes) >= 0.9)
    if inverter and c_valor:
        for t in transacoes:
            t.valor = -t.valor
    return transacoes, {"cartao": bool(inverter), "delimitador": delimitador, "saldo": None, "conta": None}


def ler_arquivo(caminho: str | Path | bytes, cartao: bool | None = None, origem: str | None = None):
    if isinstance(caminho, bytes):
        bruto, nome = caminho, origem or "bytes"
    else:
        bruto, nome = Path(caminho).read_bytes(), origem or Path(caminho).name
    texto = _decodificar(bruto)
    if "<OFX>" in texto.upper():
        return ler_ofx(texto, nome)
    return ler_csv(texto, nome, cartao)
