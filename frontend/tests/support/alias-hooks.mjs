import { existsSync } from "node:fs";

const SRC = new URL("../../src/", import.meta.url);
const CANDIDATES = ["", ".ts", "/index.ts"];

function firstExisting(base) {
  for (const suffix of CANDIDATES) {
    const url = new URL(base + suffix);
    if (existsSync(url) && !url.pathname.endsWith("/")) return url.href;
  }
  return null;
}

export async function resolve(specifier, context, next) {
  if (specifier.startsWith("@/")) {
    const found = firstExisting(new URL(specifier.slice(2), SRC).href);
    if (found) return next(found, context);
  }
  if (
    (specifier.startsWith("./") || specifier.startsWith("../")) &&
    context.parentURL?.startsWith(SRC.href) &&
    !/\.[cm]?[jt]sx?$/.test(specifier)
  ) {
    const found = firstExisting(new URL(specifier, context.parentURL).href);
    if (found) return next(found, context);
  }
  return next(specifier, context);
}
