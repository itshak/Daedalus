import { createHash } from "node:crypto";
import Image from "next/image";
import { redirect } from "next/navigation";
import { cookies, headers } from "next/headers";
import { authorizedOperator } from "@/lib/supabase";
import packageInfo from "../package.json";
import { ControlCenter } from "@/components/control-center";
import { LOCALE_COOKIE, parseLocale, translate } from "@/lib/i18n";
export const dynamic = "force-dynamic";
export default async function Home() {
  const locale = parseLocale((await cookies()).get(LOCALE_COOKIE)?.value ?? (await headers()).get("accept-language")?.split(",")[0]);
  const t = (text: string) => translate(text, locale);
  const auth = await authorizedOperator();
  if (auth.state === "not-configured")
    return <main className="setup-screen"><Image className="setup-logo" src="/brand/daedalus-logo-light.svg" alt="Daedalus" width={1200} height={930} priority /><h1>{t("Daedalus is being provisioned")}</h1><p>{t("The private administrator identity service is not configured. No account data is accessible.")}</p><a href="https://github.com/itshak/Daedalus/blob/main/apps/web/README.md">{t("Deployment checklist")}</a></main>;
  if (auth.state === "unauthenticated") redirect("/login");
  if (auth.state === "forbidden")
    return <main className="setup-screen"><Image className="setup-logo" src="/brand/daedalus-logo-light.svg" alt="Daedalus" width={1200} height={930} priority /><h1>{t("Access not granted")}</h1><p>{t("Your identity is authenticated, but an operator must explicitly approve this account. Self-registration does not confer access.")}</p><form action="/api/logout" method="POST"><button type="submit">{t("Sign out")}</button></form></main>;
  const revision=process.env.VERCEL_GIT_COMMIT_SHA;
  const scopeNamespace=createHash("sha256").update(JSON.stringify([auth.user.id,process.env.DAEDALUS_API_BASE_URL??""])).digest("hex");
  return <ControlCenter operatorId={scopeNamespace} email={auth.user.email ?? t("Administrator")} role={auth.role} webVersion={packageInfo.version} webRevision={revision&&/^[a-f0-9]{40}$/.test(revision)?revision:null} />;
}
