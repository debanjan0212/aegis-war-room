"""Code Guard agent: scans this repository for security problems and explains them in plain words.

Five checks. Each is a well-known tool or a few lines you can read below:

    code      Bandit      risky patterns in the Python code
    python    pip-audit   known vulnerabilities in Python dependencies
    web       npm audit   known vulnerabilities in JavaScript dependencies
    secrets   built-in    keys, tokens and passwords committed by mistake
    pipeline  built-in    GitHub Actions that are not pinned to an exact commit

The same scan runs from the screen (Security panel), from the terminal
(`aegis scan`) and in CI, so there is one definition of "clean".
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404 - runs the fixed scanner commands below, never text from a user or a model
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

from ..brain import get_brain
from ..settings import ROOT

LEVELS = ["info", "low", "medium", "high", "critical"]
PROMPT = (
    "You are the code guard agent. From the scanner findings, write a two-sentence summary a non-security person "
    "understands, then list the three most important fixes, most urgent first. Use only the findings given."
)
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "Hard-coded password or key",
        re.compile(r"""(?i)\b(api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*["'][^"'\s${}<>]{12,}["']"""),
    ),
]
SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "__pycache__", ".ruff_cache", ".pytest_cache"}
SKIP_FILES = {"package-lock.json", "requirements.lock"}


class GuardReport(BaseModel):
    summary: str = Field(description="two plain sentences")
    top_fixes: list[str] = Field(description="up to three fixes, most urgent first")


def _finding(tool: str, severity: str, title: str, where: str, fix: str) -> dict:
    return {"tool": tool, "severity": severity if severity in LEVELS else "medium", "title": title, "where": where, "fix": fix}


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=300)  # nosec B603 - fixed command lists only


def _bandit(root: Path) -> list[dict]:
    done = _run([sys.executable, "-m", "bandit", "-r", "aegis", "-f", "json", "-q"], root)
    return [
        _finding(
            "code", r["issue_severity"].lower(), r["issue_text"], f"{r['filename']}:{r['line_number']}", f"See {r['more_info']}"
        )
        for r in json.loads(done.stdout)["results"]
    ]


def _pip_audit(root: Path) -> list[dict]:
    command = [sys.executable, "-m", "pip_audit", "-f", "json", "--progress-spinner", "off"]
    if (root / "requirements.lock").exists():
        command += ["-r", "requirements.lock", "--require-hashes", "--disable-pip"]
    done = _run(command, root)
    report = json.loads(done.stdout)  # pip-audit prints JSON even when it finds problems
    return [
        _finding(
            "python",
            "high",
            f"{dep['name']} {dep['version']} has a known vulnerability ({vuln['id']})",
            "requirements.lock",
            f"Upgrade {dep['name']} to {', '.join(vuln['fix_versions']) or 'a fixed version when one exists'}",
        )
        for dep in report["dependencies"]
        for vuln in dep.get("vulns", [])
    ]


def _npm_audit(root: Path) -> list[dict]:
    web = root / "web"
    if not (web / "package-lock.json").exists():
        return []
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is not installed")
    report = json.loads(_run([npm, "audit", "--json"], web).stdout)
    out = []
    for name, item in report.get("vulnerabilities", {}).items():
        cause = next((via["title"] for via in item.get("via", []) if isinstance(via, dict)), "depends on a vulnerable package")
        fix = "Run `npm audit fix` in web/" if item.get("fixAvailable") else "No fix published yet. Watch for an update"
        out.append(
            _finding(
                "web",
                {"moderate": "medium"}.get(item["severity"], item["severity"]),
                f"{name}: {cause}",
                "web/package-lock.json",
                fix,
            )
        )
    return out


def _files(root: Path):
    for path in root.rglob("*"):
        if (
            path.is_file()
            and not (SKIP_DIRS & set(path.relative_to(root).parts))
            and path.name not in SKIP_FILES
            and path.stat().st_size < 1_000_000
        ):
            yield path


def _secrets(root: Path) -> list[dict]:
    out = []
    if (root / ".git").exists() and (root / ".env").exists():
        tracked = _run(["git", "ls-files", ".env"], root).stdout.strip()  # nosec B607 - git from PATH, fixed arguments
        if tracked:
            out.append(
                _finding(
                    "secrets",
                    "high",
                    "The .env file is committed to Git",
                    ".env",
                    "Remove it from Git and rotate every key in it",
                )
            )
    for path in _files(root):
        try:
            lines = path.read_text().splitlines()
        except UnicodeDecodeError:
            continue  # binary file
        for number, line in enumerate(lines, start=1):
            for kind, pattern in SECRET_PATTERNS:
                if pattern.search(line):  # the secret itself is never copied into the finding
                    out.append(
                        _finding(
                            "secrets",
                            "critical",
                            f"{kind} found in a file",
                            f"{path.relative_to(root)}:{number}",
                            "Remove it, rotate the credential, and load it from the environment instead",
                        )
                    )
    return out


def _pipeline(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            used = re.search(r"uses:\s*([^\s#]+)", line)
            if used and not used.group(1).startswith("./") and not re.search(r"@[0-9a-f]{40}$", used.group(1)):
                out.append(
                    _finding(
                        "pipeline",
                        "medium",
                        f"Action {used.group(1)} is not pinned to a commit",
                        f"{path.relative_to(root)}:{number}",
                        "Pin it to the full 40-character commit SHA. A tag can be moved to malware",
                    )
                )
    return out


CHECKS = [
    ("code", "Bandit", _bandit),
    ("python", "pip-audit", _pip_audit),
    ("web", "npm audit", _npm_audit),
    ("secrets", "built-in secret scan", _secrets),
    ("pipeline", "built-in pin check", _pipeline),
]


def offline(context: dict) -> GuardReport:
    findings = context["findings"]
    if not findings:
        return GuardReport(summary="No security problems were found by any check that ran.", top_fixes=[])
    worst = sorted(findings, key=lambda f: LEVELS.index(f["severity"]), reverse=True)
    tools = sorted({f["tool"] for f in findings})
    return GuardReport(
        summary=f"The scan found {len(findings)} issue(s) in: {', '.join(tools)}. "
        f"The most serious is rated {worst[0]['severity']}.",
        top_fixes=[f"{f['title']} ({f['where']}): {f['fix']}." for f in worst[:3]],
    )


def scan(root: Path = ROOT, model: str = "offline") -> dict:
    """Run every check and return one report. A check that cannot run is reported, never silently skipped."""
    findings, tools = [], []
    for key, label, check in CHECKS:
        try:
            found = check(root)
            findings += found
            tools.append({"check": key, "tool": label, "ran": True, "found": len(found)})
        except Exception as err:  # noqa: BLE001 - one broken scanner must not hide the others' results
            tools.append({"check": key, "tool": label, "ran": False, "problem": f"{type(err).__name__}: {err}"[:200]})
    findings.sort(key=lambda f: LEVELS.index(f["severity"]), reverse=True)
    answer, source = get_brain(model).ask(PROMPT, GuardReport, {"findings": findings[:40]}, offline)
    return {
        "scanned_at": time.time(),
        "tools": tools,
        "findings": findings,
        "summary": answer.summary,
        "top_fixes": answer.top_fixes[:3],
        "worst": findings[0]["severity"] if findings else "none",
        "complete": all(t["ran"] for t in tools),
        "answered_by": source,
    }


def fails(report: dict, level: str) -> bool:
    """True when the report has a finding at `level` or worse, or a check could not run."""
    return not report["complete"] or any(LEVELS.index(f["severity"]) >= LEVELS.index(level) for f in report["findings"])
