# his_pos_finance — contrôles Finance sur les points de vente

Met en place la procédure de gestion comptable et de contrôle des points de vente
(`docs/superpowers/specs/2026-11-24-pos-finance-controls-design.md`).

## Installation

- **Fermer toutes les caisses avant `-i`** : le module change le journal de ventes,
  le journal de caisse et la position fiscale de chaque caisse, et refuse de le
  faire si une session est ouverte.
- Donner le rôle **Finance Head** au Responsable du Département Finance.
- Renseigner le détenteur des caisses CFIN et CDIR (Comptabilité > Configuration > Journaux).

## Ce que le module pose

- Journaux VGEN / VCOP / VCAF / VRES (ventes) et CDIR / CFIN / CCOP / CCAF / CRES (caisses),
  comptes 530xxx, 581000 (virements internes, lettrable), 476000 (écarts, lettrable), 657000,
  757000, 700100 à 706200, 411xxx, 445600 / 445720.
- Une position fiscale « Revenue – <caisse> » par caisse : mêmes taxes que le régime national,
  seuls les comptes de marchandises revendues changent selon l'activité qui vend.
