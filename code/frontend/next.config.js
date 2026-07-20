/** @type {import('next').NextConfig} */

// Build piloté par variables d'environnement pour servir DEUX cibles sans
// dupliquer la config :
//
//   • Développement local (par défaut) :
//       output "standalone", servi à la racine (http://localhost:3000).
//
//   • Déploiement statique sous un sous-chemin (devweb.estia.fr/tui_assistant) :
//       NEXT_OUTPUT=export NEXT_PUBLIC_BASE_PATH=/tui_assistant npm run build
//       -> génère le dossier "out/" (HTML/JS/CSS purs) à déposer dans
//          /var/www/html/tui_assistant, servi par l'Apache existant.
//
// NEXT_PUBLIC_API_URL doit pointer vers l'API publique (figé au build) :
//   - local : http://localhost:8000
//   - prod  : https://devweb.estia.fr/tui_assistant/api
const isExport = process.env.NEXT_OUTPUT === "export";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig = {
  reactStrictMode: true,
  // basePath doit être absent (undefined) ou commencer par "/".
  basePath: basePath || undefined,
  ...(isExport
    ? {
        output: "export",
        // L'optimiseur d'images de Next exige un serveur -> désactivé en statique.
        images: { unoptimized: true },
        // Chaque route devient un dossier avec index.html -> deep-links OK sous Apache.
        trailingSlash: true,
      }
    : {
        // Build autonome (serveur Node minimal) pour le développement / l'option Docker.
        output: "standalone",
      }),
};

module.exports = nextConfig;
