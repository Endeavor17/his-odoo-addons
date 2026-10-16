#!/bin/bash
# Point d'entree de l'image : enveloppe /entrypoint.sh de l'image officielle.
#
# Au demarrage du serveur (commande exacte `odoo`) :
#   1. liste les modules installes dont le code a change depuis leur dernier -u ;
#      HIS_AUTO_UPGRADE=1 (staging) les met a jour avant de servir, sinon
#      (prod, -u manuel) on se contente de les nommer dans le log ;
#   2. rechauffe Odoo en arriere-plan (registre + bundles), voir rechauffer.py.
# Un `odoo -u|-i X --stop-after-init` lance a la main (odoo-upgrade) enregistre
# aussi l'empreinte de X s'il reussit.
set -e
ICI=/opt/his-addons/deploy/image

if [ "$*" = "odoo" ]; then
    MODS=$(python3 "$ICI/modules_modifies.py" liste)
    if [ -n "$MODS" ] && [ "${HIS_AUTO_UPGRADE:-0}" = "1" ]; then
        echo "his-entrypoint : mise a jour de $MODS"
        # Un echec arrete le conteneur : mieux vaut un staging en panne visible
        # qu'un schema perime qui sert des pages blanches.
        /entrypoint.sh odoo -u "$MODS" --stop-after-init --no-http
        python3 "$ICI/modules_modifies.py" enregistrer "$MODS"
    elif [ -n "$MODS" ]; then
        echo "WARNING his-entrypoint : modules a mettre a jour (-u manuel) : $MODS"
    fi
    python3 "$ICI/rechauffer.py" &
    exec /entrypoint.sh odoo
fi

UPD=""
prev=""
for a in "$@"; do
    case "$prev" in -u | --update | -i | --init) UPD="$a" ;; esac
    case "$a" in --update=* | --init=*) UPD="${a#*=}" ;; esac
    prev="$a"
done
if [ -n "$UPD" ] && [[ " $* " == *" --stop-after-init "* ]]; then
    /entrypoint.sh "$@"
    python3 "$ICI/modules_modifies.py" enregistrer "$UPD"
    exit 0
fi
exec /entrypoint.sh "$@"
