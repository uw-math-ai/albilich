# Vendored dashboard math renderer

MathJax 3.2.2, `es5/tex-svg-full.js`, unmodified from:
https://github.com/mathjax/MathJax/blob/3.2.2/es5/tex-svg-full.js

SHA-256: `a4354ff94fd868aea0cc6eaaa79a57fda0588646fc46ee3700a349ee0a11cbe6`

The upstream Apache-2.0 license is included in `LICENSE`. The bundle includes
its SVG font data; the dashboard needs no CDN, font fetches, npm install, or
runtime extension downloads. Its script tag pins these bytes with SRI.

The dashboard's explicit TeX package allowlist excludes HTML/URL macros,
`require`, `autoload`, and `setoptions`. Do not re-enable these for generated
proof text. The asset endpoint serves only this exact file, and the existing
nonce-only script CSP still applies. When upgrading, review the package
allowlist, update the SRI and test digest, and recheck offline math rendering.
