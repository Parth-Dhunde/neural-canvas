import { buildUrl } from "./api";
import type { HardwareInfo } from "@/types";

export async function getHardware(baseUrl: string): Promise<HardwareInfo | null> {
  try {
    const response = await fetch(buildUrl("/api/hardware", baseUrl), {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return null;
    return (await response.json()) as HardwareInfo;
  } catch {
    return null;
  }
}
