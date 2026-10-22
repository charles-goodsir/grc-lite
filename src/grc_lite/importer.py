"""Convert a notes.md downloaded from the assessor notes tool into assessment YAML.

The importer only translates. Anything it cannot map is left empty and reported as a
warning, so `grc validate` shows what still needs fixing instead of the importer guessing.
"""

import re

CELL_SPLIT = re.compile(r"(?<!\\)\|")
EV_REF = re.compile(r"\bEv?-?\s*0*(\d+)\b", re.IGNORECASE)
CRITERION_REF = re.compile(r"\bC-\d+\b")
RULE_REF = re.compile(r"[Rr]ule\s+(\d+)\W+([\w.-]+\.\w+)")
RATING = re.compile(
    r"Likelihood (\S+) \((.*)\) x Impact (\S+) \((.*)\)(?: = .*?)?(?: \[scale 1[–-](\d)\])?$"
)
ACTION = re.compile(r"^(.*) \(Owner: (.*?); Due: (.*?)\)$")
RESULTS = ["not tested", "meets", "gap", "can't test"]


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return sections


KNOWN_SECTIONS = {"Criteria sheet", "Evidence log", "Candidate findings", "Findings"}


def file_notes(text: str) -> dict[str, str]:
    """Notes typed against individual files, keyed by the path the notes tool recorded."""
    return {
        title: "\n".join(body).strip()
        for title, body in _sections(text).items()
        if title not in KNOWN_SECTIONS and "".join(body).strip()
    }


def _table(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in CELL_SPLIT.split(line.strip()[1:-1])]
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        rows.append(cells)
    return rows[1:]  # drop the header row


def _result(cell: str, row_id: str, warnings: list[str]) -> str | None:
    lowered = cell.lower().replace("can’t", "can't")
    if not lowered:
        return None
    for result in RESULTS:
        if lowered.startswith(result) or (result == "can't test" and lowered.startswith("can't")):
            return result
    warnings.append(f"{row_id}: unrecognised result '{cell[:30]}', left as not tested")
    return None


def _criteria(lines: list[str], warnings: list[str]) -> list[dict]:
    out = []
    for cells in _table(lines):
        cells += [""] * (6 - len(cells))
        cid, source, rule, needed, received, result = cells[:6]
        item = {"id": cid, "source": source, "rule": rule}
        if needed:
            item["evidence_needed"] = needed
        refs = sorted({f"E-{int(n):02d}" for n in EV_REF.findall(received)})
        if refs:
            item["evidence"] = refs
        parsed = _result(result, cid, warnings)
        if parsed:
            item["result"] = parsed
        out.append(item)
    return out


def _evidence(lines: list[str]) -> list[dict]:
    keys = ["id", "date", "source", "type", "shows", "reliability"]
    out = []
    for cells in _table(lines):
        cells += [""] * (6 - len(cells))
        item = {k: v for k, v in zip(keys, cells, strict=False) if v}
        out.append(item)
    return out


def _finding_blocks(lines: list[str]) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    current = None
    for line in lines:
        head = re.match(r"### (F-\d+): ?(.*)", line)
        if head:
            current = blocks[head.group(1)] = {"title": head.group(2).strip()}
            continue
        field = re.match(r"- \*\*(.+?):\*\* ?(.*)", line)
        if current is not None and field:
            current[field.group(1)] = field.group(2).strip()
    return blocks


def _criteria_ids(text: str, criteria: list[dict], fid: str, warnings: list[str]) -> list[str]:
    found = CRITERION_REF.findall(text)
    if not found:
        for number, filename in RULE_REF.findall(text):
            wanted = f"{filename} rule {number}".lower()
            found += [c["id"] for c in criteria if c["source"].lower().endswith(wanted)]
    if not found:  # the finding may quote the rule text verbatim
        found = [c["id"] for c in criteria if c["rule"].lower() in text.lower()]
    if not found:
        warnings.append(f"{fid}: could not match its criteria to a criterion ID")
    return list(dict.fromkeys(found))


def _apply_block(item: dict, block: dict, criteria: list[dict], warnings: list[str]) -> int | None:
    fid = item["id"]
    ids = _criteria_ids(block.get("Criteria", ""), criteria, fid, warnings)
    if ids:
        item["criteria"] = ids
    for source, target in [
        ("Condition", "condition"),
        ("Cause", "cause"),
        ("Consequence", "consequence"),
    ]:
        if block.get(source):
            item[target] = block[source]
    action = ACTION.match(block.get("Action", ""))
    if action:
        item["action"], item["owner"], item["due"] = (g.strip() for g in action.groups())
    elif block.get("Action"):
        item["action"] = block["Action"]
        warnings.append(f"{fid}: action has no 'Owner: ...; Due: ...' part")
    rating = RATING.match(block.get("Rating", ""))
    scale = None
    if rating:
        likelihood, why_l, impact, why_i, scale = rating.groups()
        for key, value in (("likelihood", likelihood), ("impact", impact)):
            if value.isdigit():
                item[key] = int(value)
        item["likelihood_reason"], item["impact_reason"] = why_l, why_i
        scale = int(scale) if scale else None
    elif block.get("Rating"):
        warnings.append(f"{fid}: could not read its rating line")
    control = block.get("Control ref", "")
    if control and control.upper() != "N/A":
        item["control_ref"] = control
    return scale


def _findings(sections: dict, criteria: list[dict], warnings: list[str]) -> tuple[list, int]:
    blocks = _finding_blocks(sections.get("Findings", []))
    scale = 3
    out = []
    for cells in _table(sections.get("Candidate findings", [])):
        cells += [""] * (5 - len(cells))
        fid, title, status, strength, why = cells[:5]
        item = {"id": fid, "title": title, "status": status, "strength": strength}
        if why:
            item["strength_reason"] = why
        if fid in blocks:
            found_scale = _apply_block(item, blocks[fid], criteria, warnings)
            scale = found_scale or scale
        elif status == "selected":
            warnings.append(f"{fid}: selected but has no write-up block")
        out.append(item)
    return out, scale


def import_notes(text: str) -> tuple[dict[str, list[dict]], int, list[str]]:
    """Return (files by name, risk scale, warnings)."""
    sections = _sections(text)
    warnings = [
        f"no '{name}' section found"
        for name in ("Criteria sheet", "Evidence log", "Candidate findings")
        if name not in sections
    ]
    criteria = _criteria(sections.get("Criteria sheet", []), warnings)
    evidence = _evidence(sections.get("Evidence log", []))
    findings, scale = _findings(sections, criteria, warnings)
    files = {"criteria": criteria, "evidence": evidence, "findings": findings}
    return files, scale, warnings


# the grading import reads the same Markdown layout
split_sections = _sections
read_table = _table
