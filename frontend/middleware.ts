import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token");
  if (!token && request.nextUrl.pathname !== "/login") return NextResponse.redirect(new URL("/login", request.url));
  if (token && request.nextUrl.pathname === "/login") return NextResponse.redirect(new URL("/", request.url));
  return NextResponse.next();
}

export const config = { matcher: ["/", "/projects/:path*", "/records/:path*", "/tasks/:path*", "/login"] };
