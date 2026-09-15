// Lint des assets JS des modules (POS, tableaux de bord OWL).
// Regles "recommended" seulement : on cherche les vraies fautes (variable non
// definie, condition toujours vraie), pas un style impose a du code Odoo/OWL.
// Le module tiers web_responsive est exclu.
import js from '@eslint/js';
import globals from 'globals';

export default [
    js.configs.recommended,
    {
        ignores: ['web_responsive/**', '**/*.min.js'],
    },
    {
        files: ['**/*.js', '**/*.esm.js'],
        languageOptions: {
            ecmaVersion: 2024,
            sourceType: 'module',
            globals: {
                ...globals.browser,
                // Fournis par le framework a l'execution.
                odoo: 'readonly',
                owl: 'readonly',
            },
        },
    },
];
