import "server-only";
import { validatedControllerOrigin } from "./request-policy";
export { allowedRequest } from "./request-policy";
export function controllerOrigin() {
  return validatedControllerOrigin(process.env.DAEDALUS_API_BASE_URL);
}
