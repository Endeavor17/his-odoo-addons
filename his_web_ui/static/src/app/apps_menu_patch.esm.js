/* Copyright 2026 Abdo Chabouti
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */

import {AppsMenu} from "@web_responsive/components/apps_menu/apps_menu.esm";
import {patch} from "@web/core/utils/patch";
import {router} from "@web/core/browser/router";
import {user} from "@web/core/user";

// Supprime le clignotement de la grille d'applications entre deux ecrans.
//
// web_responsive ouvre le tiroir des que l'URL ne porte pas encore de menu_id :
//
//     const menuId = Number(this.router.current.menu_id || 0);
//     this.state = useState({open: menuId === 0});
//
// C'est juste au premier chargement — on arrive bien sur la grille — mais faux
// partout ailleurs. En revenant du point de vente vers le back-office, l'URL
// porte une action et pas encore de menu_id : la grille s'ouvre, l'action finit
// de charger, ACTION_MANAGER:UI-UPDATED la referme. D'ou l'eclair d'un dixieme
// de seconde entre les deux ecrans.
//
// L'atterrissage legitime ne passe pas par la : WebClient._loadDefaultApp, que
// web_responsive patche aussi, ouvre le tiroir quand Odoo n'a aucune action a
// charger. C'est le bon signal, et il reste intact.
//
// Correctif dans un module a nous, jamais dans la copie de l'OCA : voir
// web_responsive/VENDOR.md.
patch(AppsMenu.prototype, {
    setup() {
        super.setup();

        if (!user.context.is_redirect_to_home || !this.state.open) {
            return;
        }

        // Une URL qui demande quelque chose de precis n'est pas un
        // atterrissage. On ferme avant le premier rendu, donc rien ne clignote.
        const current = router.current || {};
        if (current.action || current.actionStack?.length || current.resId) {
            this.state.open = false;
        }
    },
});
