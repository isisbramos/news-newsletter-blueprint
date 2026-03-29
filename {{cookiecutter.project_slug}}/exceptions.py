"""
Daily Scout — Custom exceptions por fase do pipeline.
Permite tratar cada tipo de falha de forma específica em run_pipeline().
"""


class PipelineError(Exception):
    """Base para erros do pipeline AYA."""


class FetchError(PipelineError):
    """Falha na fase de coleta: nenhuma fonte respondeu ou pre-filter zerou."""


class CurationError(PipelineError):
    """Falha na fase de curadoria: Gemini esgotou todas as tentativas."""


class DeliveryError(PipelineError):
    """Falha na fase de entrega: Buttondown não aceitou o envio.
    Não fatal — HTML já foi salvo como artefato."""
