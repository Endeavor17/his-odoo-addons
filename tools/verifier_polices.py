"""Une seule police dans l'interface : celle de his_theme.

Garde-fou de CI (consigne de Mohamed, 2026-10-08). his_theme declare les deux
familles du groupe — Figtree pour le texte, IBM Plex Mono pour les codes — et
les publie en variables CSS (--his-font-sans, --his-font-mono ; Odoo expose
aussi --font-monospace). Un module qui ecrit sa propre famille fait renaitre
le patchwork que cette regle a supprime.

Est accepte :
- une famille lue dans une variable : ``font-family: var(--his-font-mono)`` ;
- une pile qui COMMENCE par Figtree ou IBM Plex Mono : les courriels et les PDF
  ne lisent pas les variables CSS, ils doivent donc nommer la famille.

Lancer : ``python tools/verifier_polices.py`` depuis la racine du depot.
"""

import pathlib
import re
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
IGNORES = {"his_theme", "web_responsive", "helpdesk_mgmt", "helpdesk_mgmt_crm", "node_modules", "tools", "docs"}
EXTENSIONS = {".scss", ".css", ".xml", ".js"}
DECLARATION = re.compile(r"font-family\s*:\s*([^;\"}]+)", re.I)
ACCEPTE = re.compile(r"""^\s*(var\(--|inherit\b|['"]?(Figtree|IBM Plex Mono)\b)""", re.I)


def main():
    fautes = []
    for module in sorted(p for p in RACINE.iterdir() if p.is_dir() and p.name not in IGNORES):
        if not (module / "__manifest__.py").exists():
            continue
        for fichier in module.rglob("*"):
            if fichier.suffix not in EXTENSIONS or "i18n" in fichier.parts:
                continue
            for num, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), 1):
                if ligne.lstrip().startswith(("//", "*", "/*")):
                    continue
                for valeur in DECLARATION.findall(ligne):
                    if not ACCEPTE.match(valeur):
                        fautes.append(f"{fichier.relative_to(RACINE)}:{num}: font-family: {valeur.strip()}")
    if fautes:
        print("Police hors theme (utiliser var(--his-font-sans/--his-font-mono), ou commencer par Figtree) :")
        print("\n".join(fautes))
        return 1
    print("Polices : une seule famille, celle de his_theme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
