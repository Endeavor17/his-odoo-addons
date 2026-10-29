// The price above 20 pages, decided over the whole order.
//
// The rule (Mohamed, 2026-10-29): black & white PRINTS on normal paper add up
// across every document of the order; once they pass 20 pages, every one of
// those pages takes the lower price. Double-sided counts two pages a sheet, so
// 11 double-sided sheets get it. Colour never does, photocopies never do, and
// their pages do not count.
//
// A pricelist cannot say this: its minimum quantity is checked line by line,
// and a customer printing three documents of 10 pages is one job of 30.
//
// Nothing here computes a price. The lower price is the product's own
// copy_bulk_price; this module only says which of the product's two prices
// applies. Pure functions, no POS import, so the rule reads in one place.

export const BULK_THRESHOLD_PAGES = 20;

export function isBulkEligible(product) {
    return Boolean(
        product &&
            product.copy_service === "impression" &&
            product.copy_color === "bw" &&
            product.copy_paper === "normal"
    );
}

export function pagesOf(product, qty) {
    if (!isBulkEligible(product) || !(qty > 0)) {
        return 0;
    }
    return qty * (product.copy_sides === "duplex" ? 2 : 1);
}

// items: [{ product, qty }]
export function copyBulkState(items) {
    const pages = items.reduce((sum, { product, qty }) => sum + pagesOf(product, qty), 0);
    return { pages, active: pages > BULK_THRESHOLD_PAGES };
}

// The lower price when it applies, null when the line keeps its usual price.
export function bulkUnitPrice(product, active) {
    return active && isBulkEligible(product) && product.copy_bulk_price ? product.copy_bulk_price : null;
}
