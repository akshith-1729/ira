from typing import TypedDict


class AuthorRecord(TypedDict):
    id: str
    name: str


class TopicRecord(TypedDict):
    id: str
    name: str


class VenueRecord(TypedDict):
    id: str
    name: str
    kind: str


class PaperRecord(TypedDict):
    id: str
    title: str
    year: int | None
    doi: str | None
    abstract: str
    authors: list[AuthorRecord]
    topics: list[TopicRecord]
    keywords: list[str]
    venue: VenueRecord | None
    openalex_id: str | None
    arxiv_id: str | None


class ChunkRecord(TypedDict):
    id: str
    section: str
    text: str
    position: int
