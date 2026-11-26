/** Only read-only reviewed previews may use the extended request budget. */
export function isReviewPreview(parts:string[], method:string):boolean {
  return method==="POST"&&parts.length===3&&parts[0]==="accounts"&&
    ["reward-distribution-plan","shipment-plan"].includes(parts[2]);
}
export function controllerTimeout(parts:string[],method:string):number {
  return isReviewPreview(parts,method)?115000:method==="GET"?12000:25000;
}
const fillMessages=[
  "The selected account worker is disconnected or busy. Refresh account status and retry.",
  "The selected account city list could not be verified.",
  "The warehouse preview worker did not return a usable response.",
  "The owned city list changed or the warehouse observation could not be verified. Refresh city data.",
  "The selected account is not ready for a new automation. Check Activity and account status.",
  "Warehouse preview response failed validation. No transfer was started.",
  "Warehouse preview connection failed. No transfer was started.",
  "Warehouse preview access denied. Sign in again or check account permissions.",
  "Warehouse preview backend failed. No transfer was started.",
  "Warehouse preview endpoint unavailable. Check backend and website versions.",
  "Destination warehouse could not be read. Refresh city data and retry.",
  "Incoming cargo could not be verified. No transfer was started.",
  "Source city stock could not be read. Refresh city data and retry.",
  "Selected fleet is unavailable or its capacity could not be verified.",
] as const;
export function fillPreviewMessage(value:unknown):string|null {
  return typeof value==="string"&&fillMessages.some(message=>message===value)?value:null;
}

/** Translate only HTTP status classes; never expose arbitrary upstream body text. */
export function fillPreviewHttpMessage(status:number):string {
  if(status===401||status===403)return "Warehouse preview access denied. Sign in again or check account permissions.";
  if(status===404)return "Warehouse preview endpoint unavailable. Check backend and website versions.";
  if(status===502||status===504||status===524)return "Warehouse preview connection failed. No transfer was started.";
  return "Warehouse preview backend failed. No transfer was started.";
}
