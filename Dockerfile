# Image de deploiement : Odoo 19 + les modules de ce depot, figes dedans.
# Construite par la CI sur main (ghcr.io/endeavor17/his-odoo:sha-<commit>),
# promue en prod par un tag vAAAA.MM.JJ (.github/workflows/promotion.yml).
#
# Pour monter de version Odoo : changer le digest ici ET dans ci.yml (job
# tests), pour que les tests tournent sur l'image qui part en production.
FROM odoo:19.0@sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd

LABEL org.opencontainers.image.source=https://github.com/Endeavor17/his-odoo-addons

# PAS /mnt/extra-addons : l'image officielle le declare en VOLUME, et Compose
# reprend les volumes anonymes de l'ancien conteneur a chaque recreation — le
# code de la nouvelle image serait masque par l'ancien. Le odoo.conf deploye
# doit donc dire : addons_path = /opt/his-addons,/usr/lib/python3/dist-packages/odoo/addons
COPY . /opt/his-addons
