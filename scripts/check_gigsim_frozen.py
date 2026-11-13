"""CI rule: nothing under gigsim/ changed after the freeze (rules.yaml is the instructor-style configuration surface and is excluded)."""
import hashlib, pathlib, sys

files = sorted(p for p in pathlib.Path("gigsim").glob("*.py"))
h = hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()
frozen = pathlib.Path("gigsim/FROZEN.sha256")
if "--update" in sys.argv:
    frozen.write_text(h + "\n"); print("frozen", h[:12]); sys.exit(0)
if not frozen.exists() or frozen.read_text().strip() != h:
    print("gigsim/ code changed since the freeze. If intentional, run: python scripts/check_gigsim_frozen.py --update"); sys.exit(1)
print("ok: gigsim/ unchanged")
