"""Freeze hashes, the deviations ledger and manuscript checks (board nodes P2.10, P3.04, P7.10,
P11.05, P13.05, P13.07, P14.01, P15.01)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

# House style (Aaron's prose rules): no em/en dashes in prose, never the word "falsifiable".
BANNED = [(re.compile("[\u2013\u2014]"), "em/en dash"), (re.compile(r"(?<!-)---?(?!-)"), "LaTeX dash (-- or ---)"),
          (re.compile(r"\bfalsifiab\w*", re.I), "banned word 'falsifiable'")]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")) if path.is_dir() else [path]:
        if f.is_file():
            h.update(str(f.relative_to(path) if path.is_dir() else f.name).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def freeze(path: Path, ledger: Path, node: str) -> dict:
    """Record a frozen artifact's hash; refreezing with different content is a reported deviation."""
    entry = {"utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "node": node,
             "artifact": str(path), "sha256": sha256(path), "event": "freeze"}
    prior = [e for e in read_ledger(ledger) if e["artifact"] == str(path) and e["event"] == "freeze"]
    if prior and prior[-1]["sha256"] != entry["sha256"]:
        entry["event"] = "refreeze_changed"
    with ledger.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_ledger(ledger: Path) -> list[dict]:
    return [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()] if ledger.exists() else []


def verify_frozen(ledger: Path) -> list[str]:
    """Artifacts whose current hash no longer matches their last freeze."""
    last = {}
    for e in read_ledger(ledger):
        if e["event"] in ("freeze", "refreeze_changed"):
            last[e["artifact"]] = e["sha256"]
    return [a for a, h in last.items() if not Path(a).exists() or sha256(Path(a)) != h]


def search_age_months(search_log: dict, on: dt.date) -> float:
    dates = [dt.date.fromisoformat(s["searched_utc"][:10]) for s in search_log["searches"] if "error" not in s]
    return (on - min(dates)).days / 30.4375


def _strip_tex(line: str) -> str:
    line = re.sub(r"(?<!\\)%.*", "", line)  # comments
    return re.sub(r"\\(cite\w*|ref|label|url|href|eqref|input|include)\{[^}]*\}", "", line)


def lint(tex_files: list[Path]) -> list[dict]:
    findings = []
    for f in tex_files:
        for no, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            text = _strip_tex(line)
            for rx, what in BANNED:
                for m in rx.finditer(text):
                    findings.append({"file": str(f), "line": no, "rule": what, "text": text.strip()[:120], "col": m.start()})
    return findings


def pdf_text(pdf: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def fonts_not_embedded(pdf: Path) -> list[str]:
    out = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    return [ln.split()[0] for ln in out if ln.split() and len(ln.split()) >= 5 and ln.split()[-5] != "yes"]


def check_numbers(text: str, counts: dict) -> list[str]:
    """Each headline PRISMA count must appear in the manuscript text.

    Category counts ("n = 39") are legitimate elsewhere in Results, so unmatched "n = X" are not
    flagged; the flow-diagram-to-text match is what reviewers check.
    """
    flat = re.sub(r"\s+", " ", text)
    return [f"PRISMA count {key}={counts[key]} does not appear in the text"
            for key in ("identified", "screened", "assessed_full_text", "included", "excluded_full_text")
            if key in counts and not re.search(rf"\b{counts[key]}\b", flat)]


def limits(tex: Path, pdf: Path | None, profile: dict) -> dict:
    """Word, figure, table and reference counts against the journal profile."""
    res = subprocess.run(["texcount", "-inc", "-total", tex.name], capture_output=True, text=True, cwd=tex.parent)
    m = re.search(r"Words in text:\s*(\d+)", res.stdout)
    if res.returncode or not m or "File not found" in res.stdout + res.stderr:
        raise RuntimeError(f"texcount failed on {tex}: {res.stdout[-300:]}{res.stderr[-300:]}")
    words = int(m.group(1))
    src = tex.read_text()
    found = {"words": words, "figures": len(re.findall(r"\\begin\{figure\*?\}", src)),
             "tables": len(re.findall(r"\\begin\{table\*?\}|\\begin\{longtable\}", src))}
    bbl = tex.with_suffix(".bbl")
    if bbl.exists():
        found["references"] = len(re.findall(r"\\bibitem", bbl.read_text()))
    caps = {"words": profile.get("word_limit"), "figures": profile.get("max_figures"),
            "tables": profile.get("max_tables"), "references": profile.get("max_references")}
    over = {k: found[k] - v for k, v in caps.items() if v is not None and k in found and found[k] > v}
    return {"counts": found, "limits": caps, "over": over}
