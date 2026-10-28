"""spendscope — entenda seus extratos e faturas: categorias, assinaturas esquecidas, parcelas e cobranças em dobro."""

__version__ = "0.1.0"

from .analise import Parcelamento, Recorrencia
from .categorias import Categorizador, limpar_estabelecimento
from .extrato import Extrato, ler
from .leitores import ExtratoInvalido, valor_br
from .modelos import Transacao

__all__ = [
    "__version__",
    "Categorizador",
    "Extrato",
    "ExtratoInvalido",
    "Parcelamento",
    "Recorrencia",
    "Transacao",
    "ler",
    "limpar_estabelecimento",
    "valor_br",
]
