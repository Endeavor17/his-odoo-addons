# Module tiers vendu (OCA)

- Source : https://github.com/OCA/helpdesk, branche `19.0`
- Commit : `5f7f54c167e3fb3b2bf6c19271ab9519643e75f0` (2026-10-06)
- Licence : AGPL-3
- Modifications locales : **aucune**. Tout le specifique HIS vit dans
  `his_helpdesk_identity_bridge`.

Pourquoi vendu : le deploiement n'a pas d'etape de build (image `odoo:19.0`
stock, depot monte) ; rien ne peut etre installe par pip.

Mettre a jour : recopier le dossier depuis le nouveau commit OCA, changer le
commit ci-dessus, relancer la suite `his_helpdesk_identity_bridge`.
