"""Gera os arquivos de exemplo (dados fictícios) usados no README e nos testes."""

import random
from datetime import date, timedelta
from pathlib import Path

random.seed(7)
AQUI = Path(__file__).parent
inicio = date(2026, 4, 1)
lanc = []


def add(d, nome, valor, memo=None):
    lanc.append((d, nome, valor, memo))


for m in range(6):
    mes = date(2026, 4 + m, 1)
    add(mes + timedelta(days=4), "PAGAMENTO DE SALARIO", 5200.00)
    add(mes + timedelta(days=9), "PAG*NETFLIX.COM", -44.90 if m < 3 else -59.90)
    add(mes + timedelta(days=11), "SPOTIFY BR", -21.90)
    add(mes + timedelta(days=14), "DEB AUT EQUATORIAL PARA", -random.randint(180, 260) - 0.37)
    add(mes + timedelta(days=15), "DEB AUT COSANPA", -random.randint(60, 80) - 0.15)
    add(mes + timedelta(days=17), "CLARO S.A.", -119.99)
    add(mes + timedelta(days=19), "SMART FIT", -119.90)
    add(mes + timedelta(days=21), f"MAGAZINE LUIZA PARC {m + 2:02d}/10", -189.90)
    for _ in range(random.randint(6, 9)):
        dia = mes + timedelta(days=random.randint(0, 27))
        nome, faixa = random.choice(
            [
                ("IFD*IFOOD ACAI DA PRACA", (25, 70)),
                ("UBER *TRIP", (12, 38)),
                ("SUPERMERCADO FORMOSA", (80, 420)),
                ("DROGARIA PAGUE MENOS", (20, 140)),
                ("AUTO POSTO SHELL BR", (100, 250)),
                ("PADARIA NOVA ERA", (8, 35)),
                ("PIX ENVIADO MARIA SOUZA", (50, 300)),
                ("MERCADOLIVRE*VENDEDOR", (40, 260)),
            ]
        )
        add(dia, nome, -round(random.uniform(*faixa), 2))
add(date(2026, 7, 12), "UBER *TRIP", -27.40)
add(date(2026, 7, 12), "UBER *TRIP", -27.40)  # cobrança em dobro
lanc.sort(key=lambda x: x[0])

linhas = [
    "OFXHEADER:100",
    "DATA:OFXSGML",
    "VERSION:102",
    "SECURITY:NONE",
    "ENCODING:USASCII",
    "CHARSET:1252",
    "COMPRESSION:NONE",
    "OLDFILEUID:NONE",
    "NEWFILEUID:NONE",
    "",
    "<OFX>",
    "<BANKMSGSRSV1><STMTTRNRS><STMTRS>",
    "<CURDEF>BRL",
    "<BANKACCTFROM>",
    "<BANKID>0037",
    "<ACCTID>123456-7",
    "<ACCTTYPE>CHECKING",
    "</BANKACCTFROM>",
    "<BANKTRANLIST>",
    "<DTSTART>20260401",
    "<DTEND>20260930",
]
for i, (d, nome, valor, _) in enumerate(lanc):
    linhas += [
        "<STMTTRN>",
        f"<TRNTYPE>{'CREDIT' if valor > 0 else 'DEBIT'}",
        f"<DTPOSTED>{d:%Y%m%d}120000[-3:BRT]",
        f"<TRNAMT>{valor:.2f}",
        f"<FITID>{20260000 + i}",
        f"<MEMO>{nome}",
        "</STMTTRN>",
    ]
linhas += [
    "</BANKTRANLIST>",
    "<LEDGERBAL><BALAMT>3120.55<DTASOF>20260930</LEDGERBAL>",
    "</STMTRS></STMTTRNRS></BANKMSGSRSV1>",
    "</OFX>",
]
(AQUI / "conta_exemplo.ofx").write_bytes("\r\n".join(linhas).encode("cp1252"))
print(f"{len(lanc)} lançamentos → conta_exemplo.ofx")
