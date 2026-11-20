import { redirect } from "next/navigation";
import { authorizedOperator } from "@/lib/supabase";
import { ControlCenter } from "@/components/control-center";
export const dynamic = "force-dynamic";
export default async function Home() {
  const auth = await authorizedOperator();
  if (auth.state === "not-configured")
    return <main className="setup-screen"><div className="setup-icon">◇</div><h1>Daedalus is being provisioned</h1><p>The private administrator identity service is not configured. No account data is accessible.</p><a href="https://github.com/itshak/Daedalus/tree/main/openspec/changes/apple-style-nextjs-web-control-center">Deployment checklist</a></main>;
  if (auth.state === "unauthenticated") redirect("/login");
  if (auth.state === "forbidden")
    return <main className="setup-screen"><div className="setup-icon">◇</div><h1>Access not granted</h1><p>Your identity is authenticated, but an operator must explicitly approve this account. Self-registration does not confer access.</p><form action="/api/logout" method="POST"><button type="submit">Sign out</button></form></main>;
  return <ControlCenter email={auth.user.email ?? "Administrator"} role={auth.role} />;
}
