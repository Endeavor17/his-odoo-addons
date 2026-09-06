/* Verifie que chaque specialite offerte par les formulaires GHL en ligne peut
 * etre rapprochee d'un record du catalogue Odoo.
 *
 * Pourquoi ce fichier existe : le rapprochement vit dans le noeud « Rapprocher
 * la specialite » du workflow n8n, hors du depot, et il compare des libelles
 * bilingues a « name » / « name_arabe ». Rien dans Odoo ne casse si les deux
 * listes divergent — la candidature arrive simplement sans specialite, donc
 * sans domaine et sans bareme. Le 2026-09-06, les six choix Master du
 * formulaire en ligne se rapprochaient a ZERO sans que rien ne le signale.
 *
 *   node tools/test_rapprochement.mjs
 *
 * Sortie non nulle si un libelle offert ne trouve pas sa specialite.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const XML = path.join(ROOT, 'his_admission/data/his_specialite_data.xml');

/* Libelles releves dans les listes deroulantes des formulaires GHL publies.
 * Master : brZg6SmcGhxHbqfadH6h, champ « Master Field », releve le 2026-09-06.
 * Les recopier tels quels — espaces et tirets compris. */
const OFFERTES = {
  master: [
    "ماستر إدارة الأعمال - Business Administration",
    "ماستر قانون الأعمال - Droit des affaires",
    "ماستر علوم التربية - إرشاد وتوجيه - Orientation et Guidance",
    "الأمن السيبراني - Cybersécurité",
    "تسويق رقمي - Digital Marketing",
    "علم النفس العيادي - Psychologie Clinique",
  ],
  // Licence : formulaire hors saison, libelles des runs 37-39 conserves
  // comme garde-fou de non-regression.
  licence: [
    "إعلام آلي - أنظمة الإعلام الآلي",
    "Computer Systems",
    "electronique",
  ],
};

function catalogue(cycle) {
  const xml = fs.readFileSync(XML, 'utf8');
  return [...xml.matchAll(/<record\b[^>]*model="his\.specialite"[\s\S]*?<\/record>/g)]
    .map((m) => m[0])
    .map((r) => ({
      id: (/id="([^"]+)"/.exec(r) || [])[1],
      code: (/name="code">([^<]*)/.exec(r) || [])[1],
      name: (/name="name">([^<]*)/.exec(r) || [])[1],
      name_arabe: (/name="name_arabe">([^<]*)/.exec(r) || [])[1] || '',
      cycle: (/name="cycle">([^<]*)/.exec(r) || [])[1] || 'licence',
    }))
    // Le workflow interroge Odoo avec un filtre sur le cycle : une specialite
    // de l'autre cycle n'est jamais candidate au rapprochement.
    .filter((s) => s.cycle === cycle);
}

/* Copie fidele des strategies du noeud n8n. Toute divergence ici rend le test
 * menteur : en cas de doute, relire le noeud avant de toucher a ce bloc. */
const norm = (s) => (s || '')
  .toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/\s+/g, ' ')
  .trim();

// Table de mots-cles du noeud, volontairement hors service pour le Master :
// ses codes sont ceux du catalogue Licence.
const KEYWORDS = [
  ['ST-ELC',   [/electronic/i, /electroniq/i, /الإلكترونيك/, /إلكترونيك/]],
  ['INF-SEC',  [/أمن الأنظمة/, /امن الانظمة/, /securite des systemes/i, /أمن أنظمة/]],
  ['INF-SI',   [/computer system/i, /informatiq/i, /نظم المعلوماتية/, /أنظمة الإعلام/, /اعلام الي/]],
  ['ECO-GE',   [/economics.*business/i, /gestion/i, /اقتصاد/, /economie/i]],
  ['COM-ECOM', [/e-?commerce/i, /commerce/i, /التجارة/, /تجارة/]],
  ['SS-PSY',   [/clinical/i, /psycholog/i, /علم النفس/]],
  ['DR-PUB',   [/public law/i, /droit/i, /قانون/, /حقوق/]],
];

function rapprocher(cat, label, cycle) {
  label = (label || '').trim();
  if (!label) return [null, 'aucun'];
  const nl = norm(label);
  let m = cat.find((s) => norm(s.name) === nl)
       || cat.find((s) => nl && (norm(s.name).includes(nl) || nl.includes(norm(s.name))));
  if (m) return [m, 'nom'];
  m = cat.find((s) => s.name_arabe && (
    s.name_arabe.trim() === label || label.includes(s.name_arabe.trim()) || s.name_arabe.includes(label)));
  if (m) return [m, 'nom arabe'];
  if (cycle !== 'master') {
    for (const [code, pats] of KEYWORDS) {
      if (pats.some((re) => re.test(label))) {
        m = cat.find((s) => s.code === code);
        if (m) return [m, `mots-cles (${code})`];
      }
    }
  }
  for (const p of label.split(/[-–—]/).map((x) => x.trim()).filter((x) => x.length >= 4)) {
    const np = norm(p);
    m = cat.find((s) => norm(s.name).includes(np) || (s.name_arabe || '').includes(p));
    if (m) return [m, `fragment (${p})`];
  }
  return [null, 'aucun'];
}

let perdus = 0;
for (const [cycle, labels] of Object.entries(OFFERTES)) {
  const cat = catalogue(cycle);
  console.log(`\n=== ${cycle.toUpperCase()} — ${cat.length} specialites au catalogue`);
  for (const label of labels) {
    const [m, methode] = rapprocher(cat, label, cycle);
    if (!m) perdus++;
    console.log(` ${m ? 'OK   ' : 'PERDU'} ${(m ? m.code : '-').padEnd(11)} ${methode.padEnd(30)} ${label}`);
  }
}

// Un libelle vide doit produire un drapeau, jamais une exception : c'est le cas
// d'un webhook GHL dont les champs personnalises ne sont pas encore mappes.
const [vide] = rapprocher(catalogue('master'), '', 'master');
if (vide) { console.error('\nECHEC : un libelle vide a ete rapproche'); process.exit(1); }

console.log(perdus ? `\nECHEC : ${perdus} libelle(s) offert(s) sans specialite` : '\nOK : tous les libelles offerts trouvent leur specialite');
process.exit(perdus ? 1 : 0);
