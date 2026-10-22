// Les couleurs 1 a 11 du selecteur de couleur d'Odoo ($o-colors), pour que la
// matrice montre la couleur que la responsable a choisie dans l'equipe.
const PALETTE = [
    "#a2a2a2", "#ee2d2d", "#dc8534", "#e8bb1d", "#5794dd", "#9f628f",
    "#db8865", "#41a9a2", "#304be0", "#ee2f8a", "#61c36e", "#9872e6",
];

export function memberColor(index) {
    return PALETTE[index] || PALETTE[0];
}

// Texte blanc ou fonce selon la clarte du fond (luminance relative).
export function memberInk(index) {
    const hex = memberColor(index).slice(1);
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    return lum > 0.6 ? "#1d2b33" : "#ffffff";
}

export function formatHours(hours) {
    const total = Math.max(0, Math.round((hours || 0) * 60));
    return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`;
}
