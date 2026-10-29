#!/usr/bin/env node
/* Builds dist/AM_Board_Assessment_Prototype.html: one self-contained file (CSS, JS and logos inlined) that can be
   emailed, dropped in Teams or opened by double-click. Usage: node tools/build-single-file.js */
const fs = require('fs'), path = require('path');
const root = path.join(__dirname, '..'), read = f => fs.readFileSync(path.join(root, f), 'utf8');
let html = read('index.html');
html = html.replace(/<link rel="stylesheet" href="([^"]+)">/g, (m, f) => '<style>\n' + read(f) + '\n</style>');
html = html.replace(/<script src="([^"]+)"><\/script>/g, (m, f) => '<script>\n' + read(f).replace(/<\/script/gi, '<\\/script') + '\n</script>');
const uri = f => 'data:image/png;base64,' + fs.readFileSync(path.join(root, f)).toString('base64');
html = html.replace(/assets\/logo-am\.png/g, uri('assets/logo-am.png')).replace(/assets\/logo-wordmark\.png/g, uri('assets/logo-wordmark.png'));
// the inlined JS refers to the logos by path inside strings
const out = path.join(root, 'dist'); fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'AM_Board_Assessment_Prototype.html'), html);
console.log('Wrote dist/AM_Board_Assessment_Prototype.html (' + Math.round(html.length / 1024) + ' KB)');
