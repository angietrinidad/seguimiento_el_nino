"""
Post-render hook: normaliza las contrabarras de Windows en los stubs de
redirección (aliases) que genera Quarto, para que las URLs usen "/" y no "\".

Quarto en Windows escribe redirects tipo {"":"..\\amenazas\\...\\index.html"};
los navegadores toleran las contrabarras en URLs http, pero se prefieren barras.

Se ejecuta automáticamente vía project.post-render en _quarto.yml.
"""
import os, glob

out = os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "_site")
n = 0
for f in glob.glob(os.path.join(out, "**", "*.html"), recursive=True):
    try:
        t = open(f, encoding="utf-8").read()
    except Exception:
        continue
    if "var redirects = {" in t and "\\\\" in t:
        open(f, "w", encoding="utf-8").write(t.replace("\\\\", "/"))
        n += 1
print(f"[fix_redirects] stubs normalizados: {n}")
