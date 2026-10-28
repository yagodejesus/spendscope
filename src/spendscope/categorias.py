"""Limpeza de nomes de estabelecimentos e categorização automática (regras em português)."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path

from .modelos import Transacao

__all__ = ["REGRAS_SAIDA", "REGRAS_ENTRADA", "Categorizador", "limpar_estabelecimento", "extrair_parcela", "simplificar"]


def simplificar(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


# A ordem importa: a primeira regra que casar vence.
REGRAS_SAIDA: dict[str, list[str]] = {
    "Assinaturas e streaming": [
        r"netflix",
        r"spotify",
        r"disney",
        r"hbo ?max|\bmax\.com",
        r"prime ?video|amazon ?prime|amazonprime",
        r"youtube ?premium|google ?\*?youtube",
        r"deezer",
        r"globoplay",
        r"apple\.com|itunes",
        r"paramount",
        r"crunchyroll",
        r"openai|chatgpt",
        r"anthropic|claude\.ai",
        r"microsoft ?\*?365|xbox ?game ?pass",
        r"adobe",
        r"canva",
        r"icloud",
        r"dropbox",
        r"github",
        r"google ?\*?(?:one|storage|workspace)",
        r"duolingo",
    ],
    "Alimentação": [
        r"ifood|\bifd\b|ifd\*",
        r"rappi",
        r"\bze delivery|ze ?delivery",
        r"restaurante|\brest\b|churrascaria|pizzaria",
        r"lanchonete|lanches|hamburgueria|burger|mc ?donald|\bbk\b|subway|habib|bobs|outback|starbucks",
        r"padaria|panificadora|confeitaria|cafeteria|\bcafe\b|acai|sorveteria|doceria",
        r"bar e restaurante|\bbar\b",
    ],
    "Mercado": [
        r"supermercado|supermerc|mercado(?! ?(?:livre|pago))|mercearia|atacad|assai|carrefour|pao de acucar",
        r"\bextra\b|\bbig\b|mateus|\blider\b|formosa|hortifruti|sacolao|quitanda|acougue|emporio",
    ],
    "Transporte": [
        r"\buber\b|uber ?\*|uber trip",
        r"\b99 ?(?:app|pop|taxi|food)?\b|99app",
        r"cabify|indriver|in ?drive",
        r"metro|metrô|cptm|onibus|bilhete unico|passagem urbana",
        r"estacionamento|estapar|zona azul",
        r"sem ?parar|conectcar|veloe|pedagio|move ?mais",
    ],
    "Combustível": [r"\bposto\b|auto ?posto|combustive|shell|ipiranga|petrobras|\bbr mania|\bale\b|gasolina|etanol"],
    "Saúde": [
        r"farmacia|drogaria|droga ?raia|drogasil|pague ?menos|panvel|drogao|extrafarma|nissei|ultrafarma",
        r"hospital|clinica|laboratorio|consulta|medic|odonto|dentista|psicolog|fisioterap|exame",
        r"unimed|hapvida|amil|bradesco saude|sulamerica|notredame|plano de saude",
    ],
    "Casa e contas": [
        r"aluguel|condominio|iptu|imobiliaria",
        r"equatorial|enel|cemig|light\b|copel|celpe|coelba|cosern|energisa|neoenergia|celesc|cpfl|energia eletrica",
        r"cosanpa|sabesp|copasa|cedae|compesa|embasa|sanepar|caesb|saneamento|agua e esgoto",
        r"\bgas\b|ultragaz|liquigas|supergasbras|comgas",
    ],
    "Telefone e internet": [r"\bclaro\b|\bvivo\b|\btim\b|\boi\b|telefonica|internet|fibra|banda larga|\bnet\b|recarga"],
    "Educação": [r"escola|colegio|faculdade|universidade|mensalidade|curso|udemy|alura|coursera|livraria|livros|papelaria"],
    "Compras": [
        r"amazon|mercado ?livre|mercadolivre|\bmeli\b|shopee|shein|aliexpress|magalu|magazine ?luiza|americanas",
        r"casas bahia|ponto frio|kabum|renner|riachuelo|c ?& ?a\b|cea\b|zara|centauro|netshoes|leroy|havan|decathlon",
    ],
    "Lazer": [r"cinema|cinemark|ingresso|sympla|eventim|steam|playstation|\bpsn\b|nintendo|xbox|show|teatro|parque"],
    "Viagem": [r"latam|\bgol\b|azul linhas|voeazul|booking|airbnb|decolar|hotel|pousada|hostel|123 ?milhas|rodoviaria"],
    "Academia e esportes": [
        r"smart ?fit|bodytech|selfit|bluefit|academia|crossfit|pilates|natacao|gympass|wellhub|totalpass"
    ],
    "Pets": [r"petz|cobasi|pet ?shop|petshop|veterinari|racao"],
    "Impostos e taxas": [r"\bdarf\b|\bdas\b|simples nacional|ipva|licenciamento|detran|\bgru\b|receita federal|multa"],
    "Tarifas e juros": [r"tarifa|\biof\b|juros|anuidade|encargo|mora|cesta de servicos|pacote de servicos|seguro cartao"],
    "Investimentos": [r"aplicacao|\bcdb\b|tesouro|poupanca|corretora|invest|\blci\b|\blca\b|previdencia"],
    "Transferências": [r"\bpix\b|\bted\b|\bdoc\b|transferencia|transf\b"],
    "Saques": [r"saque|\batm\b|banco 24 ?h"],
}

REGRAS_ENTRADA: dict[str, list[str]] = {
    "Salário": [r"salario|folha|proventos|vencimentos|remuneracao|pro ?labore"],
    "Rendimentos": [r"rendimento|dividendo|juros sobre|\bjcp\b|resgate"],
    "Estornos e reembolsos": [r"estorno|reembolso|cashback|devolucao|chargeback"],
    "Transferências recebidas": [r"\bpix\b|\bted\b|\bdoc\b|transferencia|deposito"],
}

_PREFIXOS = re.compile(
    r"^(?:(?:compra|pagamento|pagto|pgto|pag)\s+(?:no\s+|com\s+)?(?:cart[aã]o\s+)?(?:de\s+)?(?:d[eé]bito|cr[eé]dito)?\s*"
    r"|compra\s+(?:no\s+)?(?:cart[aã]o\s+)?(?:de\s+)?(?:d[eé]bito|cr[eé]dito)?\s*"
    r"|pix\s+(?:enviado|recebido|transf\w*)\s*"
    r"|transfer[eê]ncia\s+(?:enviada|recebida)\s*(?:pelo\s+pix)?\s*"
    r"|d[eé]bito\s+autom[aá]tico\s*|deb\.?\s*aut\.?\s*|db\s+aut\s*"
    r"|(?:pag|pg|mp|mercpago|ifd|ec|ebanx|pagseguro|ps|pp|paypal|stone|sumup|cielo)\s*\*\s*)",
    re.I,
)
_PARCELA = re.compile(r"(?:parc(?:ela)?s?\.?\s*)(\d{1,2})\s*(?:/|de)\s*(\d{1,2})|[-–]\s*(\d{1,2})/(\d{1,2})\s*$", re.I)
_RUIDO = re.compile(
    r"\.com(?:\.br)?\b|\s+(?:s\.?\s?a\.?|ltda\.?|eireli|epp)$|\s+(?:-\s*)?(?:brasil|bra|br)$|\s+\d{2}/\d{2}(?:/\d{2,4})?\b|\s+\d{2}:\d{2}\b|\b\d{5,}\b|\s+-\s*$|\*+",
    re.I,
)


def extrair_parcela(descricao: str) -> tuple[int, int] | None:
    m = _PARCELA.search(descricao)
    if not m:
        return None
    atual, total = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(4)))
    return (atual, total) if 1 <= atual <= total <= 48 and total >= 2 else None


def limpar_estabelecimento(descricao: str) -> str:
    """``"COMPRA CARTAO DEB MP *ACAIDAMARIA 15/01"`` → ``"Acaidamaria"``."""
    s = _PARCELA.sub("", descricao)
    s = re.sub(r"\s+", " ", s).strip(" -–:")
    for _ in range(3):
        novo = _PREFIXOS.sub("", s).strip(" -–:")
        if novo == s:
            break
        s = novo
    s = _RUIDO.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -–:.")
    return s.title() if s.isupper() or s.islower() else s


class Categorizador:
    """Aplica regras de categoria. Suas regras (``extras``) têm prioridade sobre as padrão."""

    def __init__(self, extras: Mapping[str, Iterable[str]] | None = None) -> None:
        def compilar(regras: Mapping[str, Iterable[str]]) -> list[tuple[str, re.Pattern[str]]]:
            return [(cat, re.compile("|".join(f"(?:{p})" for p in pats), re.I)) for cat, pats in regras.items()]

        proprias = compilar({k: [v] if isinstance(v, str) else list(v) for k, v in (extras or {}).items()})
        self._saida = proprias + compilar(REGRAS_SAIDA)
        self._entrada = proprias + compilar(REGRAS_ENTRADA)

    @classmethod
    def de_arquivo(cls, caminho: str | Path) -> Categorizador:
        """Lê regras de um JSON: ``{"Academia": ["smart ?fit", "bodytech"]}``."""
        return cls(json.loads(Path(caminho).read_text(encoding="utf-8")))

    def categoria(self, descricao: str, valor) -> str:
        texto = simplificar(descricao)
        for cat, regex in self._saida if valor < 0 else self._entrada:
            if regex.search(texto):
                return cat
        return "Outros" if valor < 0 else "Outras entradas"

    def aplicar(self, transacoes: Iterable[Transacao]) -> None:
        for t in transacoes:
            t.categoria = self.categoria(f"{t.descricao} {t.estabelecimento}", t.valor)
