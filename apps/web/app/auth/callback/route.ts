import { NextRequest, NextResponse } from "next/server";
import { serverSupabase } from "@/lib/supabase";
export async function GET(request: NextRequest) {
  const redirect = NextResponse.redirect(new URL("/", request.url));
  const code = new URL(request.url).searchParams.get("code");
  const supabase = await serverSupabase();
  if (supabase && code) await supabase.auth.exchangeCodeForSession(code);
  redirect.headers.set("Cache-Control", "no-store");
  return redirect;
}
