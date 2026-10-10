"""Run from the project folder:  python make_share_zip.py

Builds SentinelAI_share.zip to send to teammates. It includes only what they need: the code, the tools, the knowledge base,
the evaluation scripts and results, and the guides. It NEVER includes your .env file (your API key), the .venv folder,
generated search indexes, memory files, caches, or any personal file that happens to sit in the folder."""
import sys
import zipfile
from pathlib import Path

ROOT = Path(".").resolve()
OUT = ROOT / "SentinelAI_share.zip"
INCLUDE_DIRS = ["app", "backend", "evaluation", "knowledge_base", "results", "evidence", "data/knowledge_base"]
INCLUDE_ROOT_SUFFIXES = {".py", ".md", ".txt"}
INCLUDE_ROOT_NAMES = {".env.example", "env.example", ".gitignore", "requirements.txt"}
NEVER_PARTS = {"__pycache__", ".venv", "venv", ".git", ".qodo", "vector_db", "vector_db_kb"}
NEVER_NAMES = {".env", "agent_memory.db"}
NEVER_SUFFIXES = {".pyc", ".db", ".sqlite3"}


def allowed(path):
    rel = path.relative_to(ROOT)
    return not (set(rel.parts) & NEVER_PARTS or path.name in NEVER_NAMES or path.suffix in NEVER_SUFFIXES)


files = []
for name in INCLUDE_DIRS:
    base = ROOT / name
    if base.is_dir():
        files += [p for p in base.rglob("*") if p.is_file() and allowed(p)]
skipped_root = []
for p in sorted(ROOT.iterdir()):
    if not p.is_file() or p == OUT:
        continue
    if (p.suffix in INCLUDE_ROOT_SUFFIXES or p.name in INCLUDE_ROOT_NAMES) and allowed(p):
        files.append(p)
    else:
        skipped_root.append(p.name)

files = sorted(set(files))
if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for p in files:
        z.write(p, p.relative_to(ROOT).as_posix())

names = zipfile.ZipFile(OUT).namelist()
unsafe = [n for n in names if n == ".env" or n.startswith(".venv/") or n.endswith(".db") or "/__pycache__/" in n]
print(f"Created {OUT.name} with {len(names)} files ({OUT.stat().st_size / 1024:.0f} KB).")
print("Key safety check:", "PASSED (no .env, .venv, memory or cache files inside)" if not unsafe else f"FAILED: {unsafe}")
if (ROOT / ".env").exists():
    print("Your .env file exists in this folder and was NOT included.")
if skipped_root:
    print("Files in the project folder that were left out on purpose:", ", ".join(skipped_root))
sys.exit(1 if unsafe else 0)
