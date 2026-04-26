import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const ALLOWED = new Set(["light", "dark"]);

async function setTheme(req: NextRequest, mode: string) {
  if (!ALLOWED.has(mode)) {
    return new NextResponse("bad mode", { status: 400 });
  }
  const c = await cookies();
  c.set("theme", mode, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    httpOnly: false,
  });
  const back =
    req.headers.get("referer") || new URL("/", req.nextUrl).toString();
  return NextResponse.redirect(back);
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ mode: string }> },
) {
  const { mode } = await ctx.params;
  return setTheme(req, mode);
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ mode: string }> },
) {
  const { mode } = await ctx.params;
  return setTheme(req, mode);
}
