const fs = require("fs");
const path = require("path");
const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "admin/index.html"), "utf8");
const js = fs.readFileSync(path.join(root, "admin/app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "admin/styles.css"), "utf8");

const checks = [
  [html.includes("adminSidebar"), "desktop sidebar"],
  [html.includes("adminNavToggle"), "mobile drawer toggle"],
  [html.includes("paymentDecisionDialog"), "payment decision dialog"],
  [js.includes("/api/admin/"), "admin API prefix"],
  [!js.includes("Authorization: Bearer"), "no main bearer auth"],
  [css.includes("@media (max-width: 760px)"), "mobile breakpoint"],
];
for (const [ok, label] of checks) {
  if (!ok) throw new Error("Admin UI smoke failed: " + label);
}
console.log("admin-ui-smoke: OK");
