"""The three prompts (planner, reranker, answer), rendered from the profile.

The *method* stays in code (rules every RAG of this shape needs: ask instead of
guessing, list every facet value that might apply, cite only real chunk ids). The
*domain* comes from the profile (catalog of values, examples, language, persona).
"""

from langchain_core.documents import Document
from langchain_core.prompt_values import PromptValue
from langchain_core.prompts import ChatPromptTemplate

from rag_observability.domain.profile import DomainProfile


def _esc(text: str) -> str:
    # Profile text goes inside a template: literal braces must not become variables.
    return text.replace("{", "{{").replace("}", "}}")


def _facet_catalog(profile: DomainProfile) -> str:
    if not profile.facets:
        return "The knowledge base has no filterable facets.\n"
    lines = ["The knowledge base can be filtered by these facets:"]
    for facet in profile.facets:
        kind = "list, every value that could apply" if facet.multiple else "single value or null"
        header = f"- {facet.name} ({kind})"
        if facet.description:
            header += f": {facet.description}"
        lines.append(header)
        for value, meaning in facet.values.items():
            lines.append(f"  - {value}: {meaning}" if meaning else f"  - {value}")
    return "\n".join(lines) + "\n"


def planner_system_prompt(profile: DomainProfile) -> str:
    a = profile.assistant
    rules = [
        "needs_clarification FIRST: does the question have more than one reasonable "
        "reading, each leading to a different answer? Then it is true — ask instead of "
        f"guessing, writing clarification_question in {a.language}. A question that "
        "simply has an answer varying across facet values is NOT ambiguous."
        + (f" {profile.planner.clarification_guidance}" if profile.planner.clarification_guidance else ""),
        f"normalized_question: rewrite the question in {a.language}, self-contained and "
        "specific, so it retrieves better.",
        "Facets are eliminatory filters: the search only looks inside the values you "
        "choose, so a wrong or missing value hides the answer. For list facets, list "
        "EVERY value that could hold the answer. When unsure, leave the facet empty — no "
        "filter is better than the wrong filter.",
        "exact_terms: literal terms worth matching (codes, product names, numbers). "
        "They are appended to the search text.",
        *profile.planner.guidance,
    ]
    text = (
        f"You plan the retrieval step of a RAG assistant for {a.domain}. "
        "You never answer the question.\n\n"
        + _facet_catalog(profile)
        + "\nRules, in order:\n"
        + "\n".join(f"{i}. {rule}" for i, rule in enumerate(rules, start=1))
    )
    if profile.planner.examples:
        text += "\n\nExamples:\n" + "\n".join(profile.planner.examples)
    return _esc(text)


def rerank_system_prompt(profile: DomainProfile) -> str:
    top_n = profile.retrieval.rerank_top_n
    return (
        "You rerank retrieved chunks for a RAG assistant. You never answer the "
        "question.\n\n"
        "Analyze only the candidate chunks below and select the ones worth sending to "
        "the answer model.\n\n"
        "Rules:\n"
        f"- Select at most {top_n} chunk_ids, best first.\n"
        "- Choose only chunks that directly help answer the question.\n"
        "- Prefer specific chunks over generic ones.\n"
        "- Prefer chunks that contain the exact terms, when given.\n"
        "- Return an empty list if no chunk supports the answer.\n"
        "- Use only Chunk IDs present in the candidates.\n\n"
        "Candidates:\n{candidates}"
    )


def answer_system_prompt(profile: DomainProfile) -> str:
    a = profile.assistant
    no_answer = _esc(profile.messages.no_answer)
    return (
        f"You are {_esc(a.persona)} for {_esc(a.domain)}. "
        "Answer the user's question using ONLY the context below. "
        "Do not use prior knowledge and do not invent information or sources.\n\n"
        "Rules:\n"
        f"- Write 'answer' in {_esc(a.language)}, objective and clear.\n"
        "- Set 'has_answer' to true only if the context supports the answer.\n"
        "- 'used_chunk_ids' must contain only Chunk IDs present in the context.\n"
        "- If the context is not enough, set 'has_answer' to false, set 'answer' to "
        f"'{no_answer}' and leave 'used_chunk_ids' empty.\n\n"
        "Context:\n{context}"
    )


class PromptSet:
    """Compiled templates for one profile."""

    def __init__(self, profile: DomainProfile) -> None:
        self.profile = profile
        self.planner = ChatPromptTemplate.from_messages(
            [("system", planner_system_prompt(profile)), ("human", "{question}")]
        )
        self.rerank = ChatPromptTemplate.from_messages(
            [
                ("system", rerank_system_prompt(profile)),
                (
                    "human",
                    "Question: {question}\n"
                    "Normalized question: {normalized_question}\n"
                    "Exact terms: {exact_terms}",
                ),
            ]
        )
        self.answer = ChatPromptTemplate.from_messages(
            [("system", answer_system_prompt(profile)), ("human", "{question}")]
        )

    def planner_prompt(self, question: str) -> PromptValue:
        return self.planner.invoke({"question": question})

    def rerank_prompt(
        self, results: list[tuple[Document, float]], question: str, plan
    ) -> PromptValue:
        return self.rerank.invoke(
            {
                "candidates": self._candidates(results),
                "question": question,
                "normalized_question": plan.normalized_question,
                "exact_terms": ", ".join(plan.exact_terms) or "none",
            }
        )

    def answer_prompt(self, documents: list[Document], question: str) -> PromptValue:
        return self.answer.invoke({"context": format_context(documents), "question": question})

    def _candidates(self, results: list[tuple[Document, float]]) -> str:
        blocks = []
        for document, _ in results:
            metadata = document.metadata
            lines = [
                f"[Chunk ID: {metadata.get('chunk_id')}]",
                f"Source: {metadata.get('source_file')}",
                f"Title: {metadata.get('title')}",
            ]
            if metadata.get("section"):
                lines.append(f"Section: {metadata['section']}")
            for field in self.profile.sources.extra_fields:
                if metadata.get(field) is not None:
                    lines.append(f"{field.replace('_', ' ').capitalize()}: {metadata[field]}")
            lines.append(f"Content:\n{document.page_content}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


def format_context(documents: list[Document]) -> str:
    # The chunk text already carries its context header (added at ingestion); the
    # model only needs the id it must cite back.
    return "\n\n".join(
        f"[Chunk ID: {d.metadata.get('chunk_id')}]\nContent:\n{d.page_content}"
        for d in documents
    )
