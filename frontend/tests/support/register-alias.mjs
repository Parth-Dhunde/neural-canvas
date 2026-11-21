// Lets `node --test` resolve the "@/..." alias and extensionless imports used in src/.
import { register } from "node:module";

register("./alias-hooks.mjs", import.meta.url);
