// Builds the dashboard and packs it into one self-contained HTML file
// (JS + CSS + data inlined) that can be opened directly from disk.
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { build } from 'esbuild';

const outDir = 'dist/export/browser';
const target = 'dist/tablero-costos-chatmigo.html';

execSync(`"${process.execPath}" node_modules/@angular/cli/bin/ng.js build --configuration production,export`, {
  stdio: 'inherit',
});

// Re-bundle main.js plus its lazy route chunks into a single classic script
const bundle = await build({
  entryPoints: [join(outDir, 'main.js')],
  bundle: true,
  format: 'iife',
  minify: true,
  write: false,
  logLevel: 'silent',
});
const js = bundle.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const css = readFileSync(join(outDir, 'styles.css'), 'utf8');

let html = readFileSync(join(outDir, 'index.html'), 'utf8')
  .replace(/<base href="[^"]*">/, '')
  .replace(/<link rel="stylesheet" href="styles\.css"[^>]*>(<noscript>.*?<\/noscript>)?/, '')
  .replace(/<link rel="modulepreload"[^>]*>/g, '')
  .replace(/<script src="[^"]*"[^>]*><\/script>/g, '');

const faviconPath = join(outDir, 'favicon.ico');
if (existsSync(faviconPath)) {
  const icon = readFileSync(faviconPath).toString('base64');
  html = html.replace(/href="favicon\.ico"/, `href="data:image/x-icon;base64,${icon}"`);
}

html = html
  .replace('</head>', () => `<style>${css}</style></head>`)
  .replace('</body>', () => `<script>${js}</script></body>`);

writeFileSync(target, html);
console.log(`\nExported ${target} (${(html.length / 1024).toFixed(0)} KB)`);
