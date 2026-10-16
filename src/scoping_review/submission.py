"""Journal profile, LaTeX template, supplement, Outbox package and run archive (board nodes P1.03,
P1.05, P9.09, P15.09, P17.03)."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

import yaml

SCHEMAS = Path(__file__).parent / "schemas"


def check_against_schema(obj: dict, schema_name: str) -> list[str]:
    """Required keys, enum values and top-level types from the schema (no jsonschema dependency)."""
    schema = json.loads((SCHEMAS / f"{schema_name}.schema.json").read_text())
    problems = [f"missing required field: {k}" for k in schema.get("required", []) if k not in obj]
    types = {"string": str, "boolean": bool, "integer": int, "number": (int, float), "object": dict, "array": list, "null": type(None)}
    for key, spec in schema.get("properties", {}).items():
        if key not in obj:
            continue
        if "enum" in spec and obj[key] not in spec["enum"]:
            problems.append(f"{key}: {obj[key]!r} not in {spec['enum']}")
        allowed = spec.get("type")
        if allowed:
            allowed = allowed if isinstance(allowed, list) else [allowed]
            if not isinstance(obj[key], tuple(types[t] for t in allowed)) or (isinstance(obj[key], bool) and "boolean" not in allowed):
                problems.append(f"{key}: expected {allowed}, got {type(obj[key]).__name__}")
        for sub in spec.get("required", []) if isinstance(obj[key], dict) else []:
            if sub not in obj[key]:
                problems.append(f"{key}: missing {sub}")
    return problems


def journal_profile(shortlist: dict, choice: dict) -> dict:
    """The chosen journal's profile from the shortlist, with the fallback order kept beside it."""
    by_name = {c["profile"]["name"]: c for c in shortlist["candidates"]}
    primary = choice["primary"]
    if primary not in by_name:
        raise ValueError(f"primary journal {primary!r} is not on the shortlist")
    unknown = [f for f in choice.get("fallbacks", []) if f not in by_name]
    if unknown:
        raise ValueError(f"fallback journals not on the shortlist: {unknown}")
    profile = by_name[primary]["profile"]
    problems = check_against_schema(profile, "journal_profile")
    if problems:
        raise ValueError(f"profile for {primary} is incomplete: {problems}")
    return {"profile": profile, "fallbacks": choice.get("fallbacks", []), "unverified": by_name[primary].get("unverified", [])}


def fetch_template(url: str | None, out: Path, fetch=None) -> list[str]:
    """Download the journal's LaTeX template (zip or single file) into out/template/."""
    if not url:
        raise ValueError("the journal profile has no latex_template_url; use the generic article template from `agsci sr assemble`")
    if fetch is None:
        from .sources import UA  # some journal sites drop Python's default User-Agent (jair.org does)
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
    else:
        data = fetch(url)
    if data.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError(f"{url} returned a web page, not a template: set latex_template_url to the download link")
    dest = out / "template"
    dest.mkdir(parents=True, exist_ok=True)
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                target = (dest / name).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise ValueError(f"unsafe path in template archive: {name}")
            z.extractall(dest)
            return z.namelist()
    name = url.rstrip("/").rsplit("/", 1)[-1] or "template.tex"
    (dest / name).write_bytes(data)
    return [name]


def supplement(search_dir: Path, charting_form: Path, included: list[dict], ft_final: list[dict], records: dict,
               out: Path) -> list[str]:
    """Supplementary files: search strings, charting form, included and excluded-at-full-text lists."""
    from .figures import latex_escape
    out.mkdir(parents=True, exist_ok=True)
    strings = [rf"\subsection*{{{latex_escape(f.stem)}}}" + "\n\\begin{verbatim}\n" + f.read_text().strip() + "\n\\end{verbatim}"
               for f in sorted(search_dir.glob("*.txt"))]
    (out / "S1_search_strategies.tex").write_text("\\section*{S1 Search strategies}\n" + "\n\n".join(strings) + "\n")
    form = yaml.safe_load(charting_form.read_text())
    rows = [rf"{latex_escape(f.get('id', ''))} & {latex_escape(f.get('label', ''))} & {latex_escape(f.get('guidance', ''))} \\"
            for f in (form if isinstance(form, list) else form.get("fields", []))]
    (out / "S2_charting_form.tex").write_text("\\section*{S2 Charting form}\n\\begin{longtable}{p{2cm}p{4cm}p{8cm}}\n"
                                              "ID & Field & Guidance \\\\ \\hline\n" + "\n".join(rows) + "\n\\end{longtable}\n")
    inc = [rf"{latex_escape(r['id'])} & {latex_escape(r.get('title', ''))} & {latex_escape(r.get('year', ''))} \\" for r in included]
    (out / "S3_included_sources.tex").write_text("\\section*{S3 Included sources}\n\\begin{longtable}{p{4cm}p{9cm}l}\n"
                                                 "ID & Title & Year \\\\ \\hline\n" + "\n".join(inc) + "\n\\end{longtable}\n")
    exc = [rf"{latex_escape(d['record_id'])} & {latex_escape(records.get(d['record_id'], {}).get('title', ''))} & {latex_escape(d['reason_code'])} \\"
           for d in ft_final if d["decision"] == "exclude"]
    (out / "S4_excluded_full_text.tex").write_text("\\section*{S4 Sources excluded at full text, with reasons}\n"
                                                   "\\begin{longtable}{p{4cm}p{8.5cm}l}\nID & Title & Reason \\\\ \\hline\n"
                                                   + "\n".join(exc) + "\n\\end{longtable}\n")
    return sorted(p.name for p in out.glob("S*.tex"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def package(files: list[Path], out: Path) -> dict:
    """Copy the submission files into one folder with a manifest; refuses to overwrite a package."""
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} already holds a package; stage a new dated folder instead")
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise ValueError(f"files missing from the package: {missing}")
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": {}}
    for f in files:
        dest = out / f.name
        shutil.copytree(f, dest) if f.is_dir() else shutil.copy2(f, dest)
        manifest["files"][f.name] = _sha(dest) if dest.is_file() else "dir"
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def archive(root: Path, out: Path) -> dict:
    """Hash every review artifact and keep the ledgers, so the run can be audited after publication."""
    files = {str(p.relative_to(root)): _sha(p) for p in sorted((root / "review").rglob("*")) if p.is_file()}
    files |= {str(p.relative_to(root)): _sha(p) for p in sorted((root / "manuscript").rglob("*")) if p.is_file()}
    manifest = {"created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": files,
                "ledgers": [k for k in files if k.endswith(("board_state.jsonl", "ai_ledger.jsonl", "ledger.jsonl"))]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1))
    return manifest
