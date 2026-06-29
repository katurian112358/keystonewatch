// Copies data files the client fetches at runtime into public/ before build.
// The nightly pipeline updates data/legislators.json; this keeps the public
// copy (what the directory + ZIP lookup fetch) in sync on every build/deploy.
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const copies = [["data/legislators.json", "public/legislators.json"]];

for (const [src, dest] of copies) {
  const srcPath = path.join(root, src);
  const destPath = path.join(root, dest);
  if (!fs.existsSync(srcPath)) {
    console.warn(`sync-public-data: missing ${src}, skipping`);
    continue;
  }
  fs.copyFileSync(srcPath, destPath);
  console.log(`sync-public-data: ${src} -> ${dest}`);
}
