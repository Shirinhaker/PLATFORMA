const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(
  path.join(__dirname, "..", "static", "index.html"),
  "utf8",
);
const checks = [
  [html.includes('id="baImageRemove"'), "business desktop image remove"],
  [html.includes('id="baMobileImageRemove"'), "business mobile image remove"],
  [html.includes('id="uaImageRemove"'), "user desktop image remove"],
  [html.includes('id="uaMobileImageRemove"'), "user mobile image remove"],
  [html.includes("ad-desktop-preview"), "desktop preview"],
  [html.includes("ad-mobile-preview"), "mobile preview"],
  [html.includes("URL.revokeObjectURL"), "preview URL cleanup"],
];
for (const [ok, label] of checks) {
  if (!ok) throw new Error("Ad upload UI smoke failed: " + label);
}
console.log("ad-upload-ui-smoke: OK");
