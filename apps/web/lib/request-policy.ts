// Pure allowlist — safe to exercise outside the Next.js runtime.
const simpleRead = new Set(["health", "accounts", "capabilities", "task-control", "account-config", "recovery"]);
const accountResources = new Set(["session", "cities", "academies", "taverns", "miracles", "shrine-status", "pirate-fortresses", "military", "ship-movements", "tasks"]);
const cityResources = new Set(["buildings", "build-options", "attack-options", "trainable-units", "workshop-upgrades", "market-quotes"]);
const safePart = /^[a-zA-Z0-9_-]{1,72}$/;
const safeNumber = /^[1-9][0-9]{0,11}$/;

export function allowedRequest(method: string, parts: string[], params: URLSearchParams): boolean {
  if (parts.some(part => !safePart.test(part))) return false;
  if (method === "GET") {
    if (parts.length === 1 && simpleRead.has(parts[0])) return true;
    if (parts.length === 2 && parts[0] === "warehouses") return true;
    if (parts.length === 3 && parts[0] === "accounts" && (accountResources.has(parts[2]) || parts[2] === "recovery")) return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "recovery" && parts[3] === "jobs") return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "tasks" && parts[3] === "preflight") return params.has("task") && (params.get("task") ?? "").length <= 96;
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "cities" && safeNumber.test(parts[3]) && cityResources.has(parts[4])) {
      if (parts[4] === "market-quotes") return ["buy", "sell_to_offers", "create_offer"].includes(params.get("side") ?? "") && /^[0-4]$/.test(params.get("resource_type") ?? "");
      return params.size === 0 || parts[4] === "trainable-units" && [...params.keys()].every(k => k === "train_troops");
    }
    return false;
  }
  if (method === "PUT") {
    return parts.length === 4 && parts[0] === "accounts" && parts[2] === "recovery" && parts[3] === "policy";
  }
  if (method === "POST") {
    if (parts.length === 3 && parts.join("/") === "recovery/policy/bulk") return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "recovery"
      && ["pause","unpause","resume-now","import-saved-token"].includes(parts[3])) return true;
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "tasks") return true;
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "cities" && safeNumber.test(parts[3]) && ["construction-plan","donation-plan","worker-plan","layout-plan","build-plan","station-plan","grind-plan","attack-plan","vacation-plan"].includes(parts[4]) && params.size === 0) return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "tasks" && ["construction-start","donation-start","worker-start","layout-start","build-start","station-start","grind-start","attack-start","vacation-start"].includes(parts[3]) && params.size === 0) return true;
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "tasks" && parts[4] === "stop") return true;
    if (parts.length === 6 && parts[0] === "accounts" && parts[2] === "tasks" && parts[3] === "requests" && parts[5] === "acknowledge") return true;
  }
  return false;
}
export function validatedControllerOrigin(raw: string | undefined): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash) return null;
    return url.origin;
  } catch { return null; }
}
