import { NextRequest, NextResponse } from "next/server";

/** Forward the current pathname as a header so Server Components can
 *  read it (used by the sidebar to highlight the active route). */
export function middleware(req: NextRequest) {
  const headers = new Headers(req.headers);
  headers.set("x-pathname", req.nextUrl.pathname);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/((?!_next/|api/lang/|favicon|.*\\.).*)"],
};
