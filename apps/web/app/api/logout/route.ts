import { NextRequest, NextResponse } from "next/server";
import { serverSupabase } from "@/lib/supabase";
export async function POST(request: NextRequest) {
  const u = new URL(request.url);
  if (request.headers.get("origin") !== u.origin)
    return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  const supabase = await serverSupabase();
  if (supabase) await supabase.auth.signOut();
  return NextResponse.json({ signedOut: true }, { headers: { "Cache-Control": "no-store" } });
}
