from __future__ import annotations
from abc import ABC, abstractmethod
from deep_translator import GoogleTranslator


class TranslationEngine(ABC):
    @abstractmethod
    def translate(self, source: str) -> str:
        raise NotImplementedError


class OnlineTranslator(TranslationEngine):
    """Prototype using an unofficial web translation wrapper; no API key needed."""
    def __init__(self) -> None:
        self.client = GoogleTranslator(source="ja", target="zh-TW")
        self.cache: dict[str, str] = {}

    def translate(self, source: str) -> str:
        source = source.strip()
        if not source:
            return ""
        if source not in self.cache:
            # Translate separately to preserve dialogue line breaks.
            translated = [self.client.translate(line) if line.strip() else ""
                          for line in source.splitlines()]
            self.cache[source] = "\n".join(translated)
        return self.cache[source]
