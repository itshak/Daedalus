import "server-only";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

export async function serverSupabase() {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  const store = await cookies();
  return createServerClient(url, key, {
    cookieOptions: { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" },
    cookies: {
      getAll() { return store.getAll(); },
      setAll(changes) {
        for (const { name, value, options } of changes) {
          try { store.set(name, value, { ...options, httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" }); }
          catch { /* Server components cannot write cookies; callback route refreshes them. */ }
        }
      }
    }
  });
}

export async function authorizedOperator() {
  const supabase = await serverSupabase();
  if (!supabase) return { state: "not-configured" as const };
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) return { state: "unauthenticated" as const };
  const { data: row, error: roleError } = await supabase.from("web_operators")
    .select("role").eq("user_id", user.id).eq("disabled", false).maybeSingle();
  if (roleError || !row || !["owner", "operator", "viewer"].includes(row.role))
    return { state: "forbidden" as const };
  return { state: "authorized" as const, user, role: String(row.role) };
}
