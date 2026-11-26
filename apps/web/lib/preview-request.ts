/** Only read-only reviewed previews may use the extended request budget. */
export function isReviewPreview(parts:string[], method:string):boolean {
  return method==="POST"&&parts.length===3&&parts[0]==="accounts"&&
    ["reward-distribution-plan","shipment-plan"].includes(parts[2]);
}
export function controllerTimeout(parts:string[],method:string):number {
  return isReviewPreview(parts,method)?115000:method==="GET"?12000:25000;
}
const fillMessages=[
  "Destination warehouse could not be read. Refresh city data and retry.",
  "Incoming cargo could not be verified. No transfer was started.",
  "Source city stock could not be read. Refresh city data and retry.",
  "Selected fleet is unavailable or its capacity could not be verified.",
] as const;
export function fillPreviewMessage(value:unknown):string|null {
  return typeof value==="string"&&fillMessages.some(message=>message===value)?value:null;
}
