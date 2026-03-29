"""
Daily Scout — Pydantic schemas para structured output do Gemini.
Separado do pipeline principal para facilitar testes e iteração.
"""

from pydantic import BaseModel, Field


class Reasoning(BaseModel):
    """Observability: registra o raciocínio editorial da AYA para debugging."""
    ai_gate_passed: list[str] = Field(
        # [PE-05] cap de 10 pra evitar token overflow — lista os mais relevantes
        description="Até 10 títulos que passaram no AI Gate (priorize os que avançaram pra seleção final)"
    )
    ai_gate_rejected_sample: list[str] = Field(
        description="3-5 exemplos de títulos rejeitados no AI Gate com motivo curto entre parênteses"
    )
    main_find_rationale: str = Field(
        description="1-2 frases: por que este item foi escolhido como main_find e não os outros"
    )
    perspective_check: str = Field(
        description="1 frase: observação sobre diversidade de fontes/perspectivas nos itens selecionados"
    )


class MainFind(BaseModel):
    title: str = Field(description="Título factual e descritivo, max 15 palavras")
    source: str = Field(
        # [SYNC-01] sem lista hardcoded — pipeline tem 10 fontes
        description="Fonte real do item — use exatamente o valor do campo 'source' no input"
    )
    body: str = Field(description="3-5 frases. Comece com atribuição à fonte. Explique o que é e por que importa pro leitor.")
    bullets: list[str] = Field(description="2-3 pontos-chave: o que aconteceu, o que significa, o que observar")
    url: str = Field(description="URL original do post")
    display_url: str = Field(description="Versão curta legível da URL")
    primary_audience: str = Field(
        description="Para quem este achado é mais relevante: 'developers', 'PMs e founders', 'business/executivos', ou 'todos'"
    )
    step5_phrase: str = Field(
        # [PE-03] enforcement estrutural do STEP 5 + audit trail
        description="Frase completada do STEP 5 que justifica a seleção deste item (ex: 'Agora é possível [ação]' ou '[Player] está [movendo pra] [categoria]')"
    )


class QuickFind(BaseModel):
    title: str = Field(description="Título curto e descritivo, max 10 palavras")
    source: str = Field(
        # [SYNC-01] sem lista hardcoded
        description="Fonte real do item — use exatamente o valor do campo 'source' no input"
    )
    signal: str = Field(description="1-2 frases curtas: [o que aconteceu] + [por que importa pro leitor]")
    url: str = Field(description="URL original")
    display_url: str = Field(description="Versão curta da URL")
    primary_audience: str = Field(
        description="Para quem este achado é mais relevante: 'developers', 'PMs e founders', 'business/executivos', ou 'todos'"
    )
    step5_phrase: str = Field(
        # [PE-03] enforcement estrutural do STEP 5
        description="Frase completada do STEP 5 que justifica a seleção deste item"
    )


class RadarItem(BaseModel):
    title: str = Field(description="Título curto e descritivo, max 10 palavras")
    source: str = Field(
        description="Fonte real do item — use exatamente o valor do campo 'source' no input"
    )
    why_watch: str = Field(description="1 frase: por que vale acompanhar nos próximos dias (tom de 'cedo demais pra conclusão, mas...')")
    url: str = Field(description="URL original")
    display_url: str = Field(description="Versão curta da URL")


class Meta(BaseModel):
    total_analyzed: int = Field(description="Número total de posts analisados (use o valor informado no contexto do dia)")
    sources_used: list[str] = Field(description="Lista de fontes usadas")
    editorial_note: str = Field(default="", description="Observação opcional sobre o dia")


class CurationOutput(BaseModel):
    reasoning: Reasoning = Field(description="Raciocínio editorial — explique suas decisões de seleção")
    correspondent_intro: str = Field(description="1-2 frases em primeira pessoa. A primeira frase referencia o achado do dia pelo tema; a segunda pode citar volume (X posts de Y fontes).")
    main_find: MainFind
    quick_finds: list[QuickFind] = Field(description="3-5 achados rápidos")
    radar: list[RadarItem] = Field(default_factory=list, description="1-2 itens de early signal — temas emergentes que ainda não são achados mas valem acompanhar")
    meta: Meta
