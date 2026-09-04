"""Regenerate the claude.ai Project bundle from references/ (spec section 6.9)."""
import shutil, zipfile
from pathlib import Path
from . import io

KNOWLEDGE = {  # reference file -> bundle name
    "01-brand-kit.md": "01-brand-kit.md",
    "02-google-ads-architecture.md": "02-google-ads-architecture.md",
    "03-merchant-center-standards.md": "03-merchant-center-standards.md",
    "04-ad-copy-frameworks.md": "04-ad-copy-frameworks.md",
    "05-creative-production-system.md": "05-creative-production-system.md",
    "06-google-audit-checklist.md": "06-google-audit-checklist.md",
    "07-conversion-tracking-execution.md": "07-conversion-tracking-execution.md",
    "08-mcp-and-gaql-notes.md": "08-mcp-and-gaql-notes.md",
    "09-project-instructions.md": "09-PROJECT-INSTRUCTIONS.md",
}
PROMPTS = "10-prompts.md"

def build(references_dir, assets_dir, out_dir, stale=None):
    """Write the knowledge files, prompts.md, SETUP.md, and the zip into out_dir.

    stale, when given a list, has any *.md file already present in out_dir/knowledge
    that this run did not write appended to it (sorted by name). Those files are
    left on disk untouched and excluded from the zip; only files this run wrote
    are zipped, never a glob of whatever happens to be in the folder.
    """
    references_dir, assets_dir, out_dir = Path(references_dir), Path(assets_dir), Path(out_dir)
    k = out_dir / "knowledge"
    k.mkdir(parents=True, exist_ok=True)
    written = []
    written_knowledge = []
    for src, dst in KNOWLEDGE.items():
        s = references_dir / src
        if not s.exists():
            raise io.MissingInput(f"reference missing: {s}")
        shutil.copyfile(s, k / dst)
        written.append(k / dst)
        written_knowledge.append(k / dst)
    prompts_src = references_dir / PROMPTS
    if not prompts_src.exists():
        raise io.MissingInput(f"reference missing: {prompts_src}")
    shutil.copyfile(prompts_src, out_dir / "prompts.md"); written.append(out_dir / "prompts.md")
    setup_src = assets_dir / "SETUP.md"
    if not setup_src.exists():
        raise io.MissingInput(f"reference missing: {setup_src}")
    shutil.copyfile(setup_src, out_dir / "SETUP.md"); written.append(out_dir / "SETUP.md")

    if stale is not None:
        written_names = {p.name for p in written_knowledge}
        stale.extend(f for f in sorted(k.glob("*.md")) if f.name not in written_names)

    z = out_dir / "google-ads-claude-project.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(written_knowledge, key=lambda p: p.name):
            zf.write(f, "knowledge/" + f.name)
        zf.write(out_dir / "prompts.md", "prompts.md")
        zf.write(out_dir / "SETUP.md", "SETUP.md")
    written.append(z)
    return written

def cmd_bundle(args):
    root = Path(__file__).resolve().parents[1]
    out = Path(args.out).expanduser()
    stale = []
    paths = build(root / "references", root / "assets", out, stale=stale)
    print(f"bundle: {len(paths)} files -> {out}")
    if stale:
        names = ", ".join(p.name for p in stale)
        print(f"bundle: {len(stale)} stale file(s) in {out / 'knowledge'} not written by this run and not in the zip: {names}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("bundle", help="regenerate the claude.ai Project bundle from references/")
    p.add_argument("--out", default="~/gads/_bundle")
    p.set_defaults(func=cmd_bundle)
