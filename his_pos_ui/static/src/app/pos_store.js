import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

// Core sends an idle till to the screen saver after 5 minutes, and waking it
// drops the cashier, so pos_hr asks for the PIN again. Between two customers at
// a counter that is most of the day: the till waits an hour instead. Matched on
// core's value so the other steps (login screen, restaurant floor) keep theirs.
const CORE_SAVER_TIMEOUT = 5 * 60 * 1000;
const HIS_SAVER_TIMEOUT = 60 * 60 * 1000;

patch(PosStore.prototype, {
    get idleTimeout() {
        return super.idleTimeout.map((step) =>
            step.timeout === CORE_SAVER_TIMEOUT ? { ...step, timeout: HIS_SAVER_TIMEOUT } : step
        );
    },
});
