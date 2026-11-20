import "server-only";

const simpleRead = new Set(["health", "accounts", "capabilities", "task-control", "account-config"]);
const accountResources = new Set([
  "session", "cities", "academies", "taverns", "miracles", "shrine-status",
  "pirate-fortresses", "military", "ship-movements", "tasks"
]);
const cityResources = new Set(["buildings", "trainable-units", "workshop-upgrades", "market-quotes"]);
const safePart = /^[a-zA-Z0-9_-]{1,72}$/;
const safeNumber = /^[1-9][0-9]{0,11}$/;

export function allowedRequest(method: string, parts: string[], params: URLSearchParams): boolean {
  if (parts.some(p => !safePart.test(p))) return false;
  if (method === "GET") {
    if (parts.length === 1 && simpleRead.has(parts[0])) return true;
    if (parts.length === 2 && parts[0] === "warehouses") return true;
    if (parts.length === 3 && parts[0] === "accounts" && accountResources.has(parts[2])) return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "tasks" && parts[3] === "preflight") {
      return params.has("task") && (params.get("task") ?? "").length <= 96;
    }
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "cities" && safeNumber.test(parts[3]) && cityResources.has(parts[4])) return true;
    return false;
  }
  if (method === "POST") {
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "tasks") return true;
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "cities" && safeNumber.test(parts[3]) && parts[4] === "construction-preview") return true;
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "tasks" && parts[4] === "stop") return true;
    if (parts.length === 6 && parts[0] === "accounts" && parts[2] === "tasks" && parts[3] === "requests" && parts[5] === "acknowledge") return true;
    return false;
  }
  if (method === "PUT") return parts.length === 1 && parts[0] === "account-config";
  return false;
}

export function controllerOrigin() {
  const raw = process.env.DAEDALUS_API_BASE_URL;
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash) return null;
    return url.origin;
  } catch { return null; }
}
