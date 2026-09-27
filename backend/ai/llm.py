import logging

from openai import OpenAI

from ai.prompts import (
    ASK_TASK,
    CONCEPT_TASK,
    KEYWORD_TASK,
    SUMMARY_TASK,
    gap_task,
    neighbor_concept_task,
    parse_json,
    query_task,
    search_brief_task,
)
from config import Settings

log = logging.getLogger(__name__)


class LLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._groq = None
        self._cerebras = None

    def _client(self, batch: bool) -> tuple[OpenAI, str]:
        # Generation always goes to Groq. Cerebras stays wired but unused.
        if batch:
            if not self.settings.cerebras_api_key:
                raise RuntimeError("CEREBRAS_API_KEY is not set")
            if self._cerebras is None:
                self._cerebras = OpenAI(
                    api_key=self.settings.cerebras_api_key,
                    base_url=self.settings.cerebras_base_url,
                )
            return self._cerebras, self.settings.cerebras_model
        if not self.settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        if self._groq is None:
            self._groq = OpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.groq_base_url,
            )
        return self._groq, self.settings.groq_model

    def complete(self, prefix: str, instruction: str, *, fast: bool = False, batch: bool = False) -> dict:
        client, model = self._client(batch)
        if fast and not batch:
            model = self.settings.groq_fast_model
        # The paper text is the leading block so provider prefix caches can reuse it.
        content = f"{prefix}\n\nTASK:\n{instruction}"
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[{"role": "user", "content": content}],
        )
        text = response.choices[0].message.content or ""
        return parse_json(text)

    def summarize(self, prefix: str) -> dict:
        return self.complete(prefix, SUMMARY_TASK)

    def narrate_gaps(self, prefix: str, diff: list[dict]) -> dict:
        return self.complete(prefix, gap_task(diff))

    def answer(self, prefix: str, question: str) -> dict:
        # The section text and its ids are already in the prefix, so the question alone
        # keeps that block byte-identical and cacheable across questions.
        return self.complete(prefix, f"{ASK_TASK}\n\nQUESTION:\n{question}")

    def keywords(self, prefix: str) -> list[str]:
        payload = self.complete(prefix, KEYWORD_TASK, fast=True)
        values = payload.get("keywords") or []
        return [str(item).strip() for item in values if str(item).strip()]

    def concepts(self, prefix: str) -> list[dict]:
        payload = self.complete(prefix, CONCEPT_TASK, fast=True)
        return [item for item in (payload.get("concepts") or []) if isinstance(item, dict)]

    def interpret_query(self, query: str) -> dict:
        return self.complete("", query_task(query), fast=True)

    def narrate_search(self, query: str, intent: dict, rows: list[dict]) -> dict:
        return self.complete("", search_brief_task(query, intent, rows), fast=True)

    def neighbor_concepts(self, neighbors: list[dict]) -> dict[str, list[dict]]:
        if not neighbors:
            return {}
        payload = self.complete("", neighbor_concept_task(neighbors), fast=True)
        out: dict[str, list[dict]] = {}
        for row in payload.get("papers") or []:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            out[row["id"]] = [item for item in (row.get("concepts") or []) if isinstance(item, dict)]
        return out
