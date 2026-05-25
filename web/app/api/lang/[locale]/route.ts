import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const ALLOWED = new Set(["th", "en"]);

async function setLocale(req: NextRequest, locale: string) {
  if (!ALLOWED.has(locale)) {
    return new NextResponse("Bad locale", { status: 400 });
  }
  const c = await cookies();
  c.set("lang", locale, {
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
  ctx: { params: Promise<{ locale: string }> },
) {
  const { locale } = await ctx.params;
  return setLocale(req, locale);
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ locale: string }> },
) {
  const { locale } = await ctx.params;
  return setLocale(req, locale);
}
