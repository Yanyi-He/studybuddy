"""A deliberately bounded Markdown extractor, not a Markdown rendering engine."""

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Any

import yaml
from yaml.events import AliasEvent

from studybuddy.models import Heading, ParsedNote, WikiLink

ATX = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$")
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
INLINE_CODE = re.compile(r"(`+).*?\1")


class BoundedLoader(yaml.SafeLoader):
    """SafeLoader plus bounds for untrusted YAML; aliases are intentionally unsupported."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.depth = 0
        self.nodes = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        self.nodes += 1
        if self.check_event(AliasEvent) or self.depth >= 24 or self.nodes > 2048:
            raise yaml.YAMLError("YAML aliases or complexity limits exceeded")
        self.depth += 1
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1


def _json_date(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError("Unsupported metadata value")


def _frontmatter(lines: list[str]) -> tuple[dict[str, Any], int, list[str]]:
    if not lines or lines[0].strip() != "---":
        return {}, 0, []
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None)
    if closing is None:
        return {}, len(lines), ["unclosed_frontmatter"]
    raw = "\n".join(lines[1:closing])
    if len(raw) > 65536:
        return {}, closing + 1, ["frontmatter_too_large"]
    try:
        metadata = yaml.load(raw, Loader=BoundedLoader)
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict) or not all(isinstance(key, str) for key in metadata):
            raise yaml.YAMLError("Frontmatter must be a string-keyed mapping")
        json.dumps(metadata, default=_json_date, sort_keys=True, allow_nan=False)
        return metadata, closing + 1, []
    except (yaml.YAMLError, TypeError, ValueError, RecursionError):
        return {}, closing + 1, ["invalid_yaml"]


def _visible_lines(lines: list[str], start: int) -> list[tuple[int, str]]:
    text = "\n".join(lines[start:])
    text = COMMENT.sub(lambda match: "\n" * match.group().count("\n"), text)
    visible = []
    fence_char, fence_size = "", 0
    for number, line in enumerate(text.split("\n"), start + 1):
        marker = FENCE.match(line)
        if marker:
            run, suffix = marker.groups()
            if not fence_char:
                fence_char, fence_size = run[0], len(run)
            elif run[0] == fence_char and len(run) >= fence_size and not suffix.strip():
                fence_char = ""
            visible.append((number, ""))
        else:
            visible.append((number, line if not fence_char else ""))
    return visible


def _headings(visible: list[tuple[int, str]]) -> tuple[Heading, ...]:
    found: list[Heading] = []
    occurrences: Counter[str] = Counter()
    for index, (line_number, line) in enumerate(visible):
        atx = ATX.match(line)
        title = re.sub(r"[ \t]+#+[ \t]*$", "", atx[2]).strip() if atx else ""
        if (
            not atx
            and index + 1 < len(visible)
            and line.strip()
            and not line.startswith(("    ", "\t"))
            and SETEXT.match(visible[index + 1][1])
        ):
            title = line.strip()
        if title:
            occurrences[title] += 1
            found.append(Heading(title, title, f"{title}\x1f{occurrences[title]}", line_number))
    return tuple(found)


def _links(visible: list[tuple[int, str]]) -> tuple[WikiLink, ...]:
    found = []
    for line_number, line in visible:
        if line.startswith(("    ", "\t")):
            continue
        for match in WIKILINK.finditer(INLINE_CODE.sub("", line)):
            destination, _, alias = match[1].partition("|")
            target, _, anchor = destination.partition("#")
            found.append(WikiLink(target.strip(), anchor.strip(), alias.strip(), line_number))
    return tuple(found)


def parse_note(text: str, relative_path: str) -> ParsedNote:
    lines = text.lstrip("\ufeff").splitlines()
    metadata, start, warnings = _frontmatter(lines)
    visible = _visible_lines(lines, start)
    headings = _headings(visible)
    if not headings:
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            title = PurePosixPath(relative_path).stem
        headings = (Heading(title.strip(), "", "__document__", start + 1),)
    return ParsedNote(
        json.dumps(
            metadata, ensure_ascii=False, default=_json_date, sort_keys=True, allow_nan=False
        ),
        headings,
        _links(visible),
        tuple(warnings),
    )
