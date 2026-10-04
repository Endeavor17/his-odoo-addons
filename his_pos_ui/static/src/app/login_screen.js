import { LoginScreen } from "@point_of_sale/app/screens/login_screen/login_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// The login screen's way out reads "Return", like the menu item (navbar.xml).
// While a PIN is being typed pos_hr turns the same button into "Discard": that
// case is left to super, so it holds whichever of the two patches runs last.
patch(LoginScreen.prototype, {
    get backBtnName() {
        return this.pos.login && this.pos.config.module_pos_hr ? super.backBtnName : _t("Return");
    },
});
