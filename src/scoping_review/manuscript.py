"""Manuscript assembly and gates (board nodes P8.16, P9.09, P9.10, P9.11, P10.07, P11.06, P12.01d,
P13.07, P14.02, P14.05)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

CHECKLISTS = Path(__file__).parent / "checklists"
CITE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def cite_keys(tex: str) -> set[str]:
    return {k.strip() for m in CITE.finditer(tex) for k in m.group(1).split(",") if k.strip()}


def all_tex(root: Path, main: str = "main.tex") -> str:
    """main.tex plus everything it \\input s or \\include s, recursively; stray files (backups,
    other sources) in the directory are not part of the manuscript and are ignored."""
    seen, parts = set(), []

    def walk(path: Path):
        if path in seen or not path.exists():
            return
        seen.add(path)
        text = path.read_text(errors="replace")
        parts.append(text)
        for m in re.finditer(r"^[^%\n]*\\(?:input|include)\{([^}]+)\}", text, re.M):
            name = m.group(1)
            walk(root / (name if name.endswith(".tex") else name + ".tex"))

    walk(root / main)
    if not parts:
        raise FileNotFoundError(root / main)
    return "\n".join(parts)


def audit_claims(claims: dict, included_ids: set[str], stats_keys: set[str], tex: str | None,
                 cite_key_of: dict[str, str]) -> list[str]:
    """Every claim cites included records (or a stats key); with the manuscript, every claim's
    citations appear in it, and every cited included record is grounded by some claim."""
    problems = []
    for i, c in enumerate(claims["claims"]):
        if not c.get("source_ids"):
            problems.append(f"claim {i}: no source_ids: {c['claim'][:80]!r}")
        for sid in c.get("source_ids", []):
            if sid.startswith("stats:"):
                if sid[len("stats:"):] not in stats_keys:
                    problems.append(f"claim {i}: unknown stats key {sid}")
            elif sid not in included_ids:
                problems.append(f"claim {i}: {sid} is not an included source")
    if tex is not None:
        used = cite_keys(tex)
        for i, c in enumerate(claims["claims"]):
            missing = [k for k in c.get("citation_keys", []) if k not in used]
            if missing:
                problems.append(f"claim {i}: citation keys not in the manuscript: {missing}")
        grounded = {sid for c in claims["claims"] for sid in c.get("source_ids", [])}
        key_to_id = {v: k for k, v in cite_key_of.items()}
        for key in sorted(used):
            rid = key_to_id.get(key)
            if rid and rid not in grounded:
                problems.append(f"included source {rid} ({key}) is cited but grounds no claim")
    return problems


def stats_keys(stats: dict) -> set[str]:
    keys = {"n_sources"}
    for field, f in stats.get("fields", {}).items():
        keys |= {f"fields.{field}.counts.{k}" for k in f["counts"]}
    return keys


def assemble(outline_sections: list[str], out: Path, bib: str = "references") -> str:
    """Draft main.tex (article class) including the drafted sections in outline order.

    P13.01 later ports this to the journal class; until then this is what compiles and is audited.
    """
    body = "\n".join(rf"\input{{sections/{s}}}" for s in outline_sections if s != "abstract")
    tex = "\n".join([
        r"\documentclass[11pt]{article}",
        r"\usepackage[T1]{fontenc}", r"\usepackage{graphicx}", r"\usepackage{booktabs}", r"\usepackage{longtable}",
        r"\usepackage{pdflscape}", r"\usepackage[numbers]{natbib}", r"\usepackage{hyperref}",
        r"\begin{document}", r"\begin{abstract}", r"\input{sections/abstract}", r"\end{abstract}", body,
        r"\bibliographystyle{plainnat}", rf"\bibliography{{{bib}}}", r"\end{document}", ""])
    out.write_text(tex)
    return tex


def check_refs(tex: str, bib_text: str, retractions: list[dict]) -> list[str]:
    from .bib import entries
    keys = set(entries(bib_text))
    used = cite_keys(tex)
    problems = [f"dangling citation: {k}" for k in sorted(used - keys)]
    problems += [f"orphan bib entry: {k}" for k in sorted(keys - used)]
    problems += [f"retracted source cited: {r['doi']} ({r['notices']})" for r in retractions if r["retracted"]]
    return problems


IGNORE_ACRONYMS = {"AND", "OR", "NOT", "NEAR", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}


def proof_auto(log: str, tex: str, spell_lang: str = "en_US", wordlist: set[str] = frozenset()) -> list[str]:
    """Faults a script can find reliably: unresolved references, duplicate labels, doubled words,
    acronyms used but never defined, and lowercase misspellings (aspell, LaTeX mode).

    Capitalised words are left to the human proofread: in a review they are mostly names of
    authors, systems and datasets, which a dictionary cannot judge.
    """
    out = [f"log: {m.strip()}" for m in re.findall(r"(LaTeX Warning: (?:Reference|Citation) .*? undefined.*)", log)]
    out += [f"log: {m.strip()}" for m in re.findall(r"(LaTeX Warning: Label .* multiply defined.*)", log)]
    prose = re.sub(r"(?<!\\)%.*", "", tex)
    prose = re.sub(r"^\s*\\(?:re)?newcommand.*$|^\s*\\def\\.*$", "", prose, flags=re.M)  # macro definitions
    brace = r"\{(?:[^{}]|\{[^{}]*\})*\}"  # one level of nesting covers specs like {@{}lcc@{}}
    prose = re.sub(rf"\\begin\{{(?:tabular\*?|longtable|tabularx)\}}(?:{brace})?{brace}", " ", prose)  # column specs
    text = re.sub(r"\$[^$]*\$", " ", prose)  # inline math is not prose
    out += [f"doubled word: '{m.group(0)}'" for m in re.finditer(r"\b([A-Za-z]{2,})\s+\1\b", text, re.I)]
    defined = set(re.findall(r"\(([A-Z][A-Z]{1,6})s?\)", text))
    used = set(re.findall(r"\b([A-Z]{2,7})s?\b", re.sub(r"\\[a-zA-Z]+\*?(\[[^]]*\])?(\{[^}]*\})?", " ", text)))
    out += [f"acronym never defined: {a}" for a in sorted(used - defined - IGNORE_ACRONYMS - set(wordlist))]
    words = subprocess.run(["aspell", "list", "--mode=tex", f"--lang={spell_lang}"], input=text,
                           capture_output=True, text=True, check=True).stdout.split()
    out += [f"spelling: {w}" for w in sorted({w for w in words if w.islower() and w not in wordlist})]
    return out


def page_of_labels(aux: str) -> dict[str, str]:
    """\\newlabel{key}{{num}{page}...} lines in main.aux give the page of every label."""
    return {m.group(1): m.group(2) for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{[^}]*\}\{([^}]*)\}", aux)}


def checklist(name: str, reporting_map: dict, aux: str) -> tuple[str, list[str]]:
    """Reporting checklist as LaTeX with page numbers taken from main.aux; returns (tex, problems)."""
    found = sorted(CHECKLISTS.parent.parent.glob(f"*/checklists/{name}.yaml"))  # any research type's checklists
    if len(found) != 1:
        raise ValueError(f"checklist {name!r} not found exactly once under src/*/checklists: {found}")
    items = yaml.safe_load(found[0].read_text())
    pages = page_of_labels(aux)
    rows, problems = [], []
    mapping = {str(k): v for k, v in reporting_map.items()}
    for it in items["items"]:
        entry = mapping.get(str(it["n"]))
        if entry is None:
            problems.append(f"item {it['n']} ({it['name']}) is not mapped to a label or 'na'")
            where = "?"
        elif str(entry).startswith("na"):
            if not it.get("if_done"):
                problems.append(f"item {it['n']} ({it['name']}) is required but marked na")
            where = "n/a"
        elif entry in pages:
            where = pages[entry]
        else:
            problems.append(f"item {it['n']}: label {entry!r} not found in main.aux")
            where = "?"
        rows.append(rf"{it['section']} & {it['n']} & {it['name']} & {where} \\")
    tex = "\n".join([r"\documentclass[10pt]{article}", r"\usepackage[margin=2cm]{geometry}", r"\usepackage{longtable,booktabs}",
                     r"\begin{document}", rf"\section*{{{items['name']} checklist ({items['version']})}}",
                     r"\begin{longtable}{p{2.6cm}rp{8.5cm}l}", r"\toprule Section & Item & Checklist item & Page \\ \midrule \endhead",
                     *rows, r"\bottomrule", r"\end{longtable}", r"\end{document}", ""])
    return tex, problems
