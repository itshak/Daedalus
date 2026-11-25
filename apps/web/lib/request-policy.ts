// Pure allowlist — safe to exercise outside the Next.js runtime.
import {challengeRoute} from "./challenge-policy.ts";
import {extensionRoute} from "./extension-settings.ts";
import {notificationRoute} from "./notification-settings.ts";
import {REVIEW_START_ROUTES} from "./generated-operation-contract.ts";
const simpleRead = new Set(["health", "accounts", "capabilities", "task-control", "account-config", "recovery"]);
const accountResources = new Set(["session", "cities", "academies", "taverns", "miracles", "shrine-status", "pirate-fortresses", "military", "ship-movements", "tasks"]);
const cityResources = new Set(["buildings", "build-options", "attack-options", "trainable-units", "workshop-upgrades", "market-quotes"]);
const safePart = /^[a-zA-Z0-9_-]{1,72}$/;
const safeNumber = /^[1-9][0-9]{0,11}$/;

export function allowedRequest(method: string, parts: string[], params: URLSearchParams): boolean {
  if (parts.some(part => !safePart.test(part))) return false;
  if (method === "GET") {
    if (extensionRoute(parts)||challengeRoute(parts)) return params.size===0;
    if (parts.join("/") === "release-status") return params.size===0;
    if (parts.length === 1 && simpleRead.has(parts[0])) return true;
    if (parts.length === 2 && parts[0] === "warehouses") return true;
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "world-reports") return params.size===0;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "world-reports" && /^[a-f0-9]{24}$/.test(parts[3])) return params.size===1 && /^(?:0|[1-9][0-9]{0,4})$/.test(params.get("offset")??"") && Number(params.get("offset"))<=10201;
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "administrative-status") return params.size===0;
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "activity")
      return [...params.keys()].every(k=>["before","limit","status"].includes(k)&&params.getAll(k).length===1)
        && (!params.has("before")||(/^[1-9][0-9]{0,15}$/.test(params.get("before")??"")&&Number.isSafeInteger(Number(params.get("before")))))
        && (!params.has("limit")||/^(?:[1-9][0-9]?|100)$/.test(params.get("limit")??""))
        && (!params.has("status")||["all","dispatching","started","rejected","unconfirmed","operator_reconciled"].includes(params.get("status")??""));
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "island-destinations") return params.size===2 && ["x","y"].every(k=>/^(?:[1-9][0-9]?|100)$/.test(params.get(k)??""));
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
    if (extensionRoute(parts)||challengeRoute(parts)) return params.size===0;
    if (notificationRoute(parts)) return params.size===0;
    if (parts.join("/") === "tasks/reviewed-batch-check") return params.size===0;
    if (parts.length === 3 && parts.join("/") === "recovery/policy/bulk") return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "recovery"
      && ["pause","unpause","resume-now","import-saved-token"].includes(parts[3])) return true;
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "shipment-plan") return params.size===0;
    if (parts.length === 3 && parts[0] === "accounts" && parts[2] === "tasks") return true;
    if (parts.length === 5 && parts[0] === "accounts" && parts[2] === "cities" && safeNumber.test(parts[3]) && ["training-plan","construction-plan","donation-plan","worker-plan","layout-plan","build-plan","station-plan","grind-plan","attack-plan","vacation-plan"].includes(parts[4]) && params.size === 0) return true;
    if (parts.length === 4 && parts[0] === "accounts" && parts[2] === "tasks" && REVIEW_START_ROUTES.includes(parts[3]) && params.size === 0) return true;
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
