import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const authSession = request.cookies.get('auth_session');
    const { pathname } = request.nextUrl;

    // 1. Protect Dashboard Routes
    if (pathname.startsWith('/dashboard')) {
        if (!authSession) {
            return NextResponse.redirect(new URL('/', request.url));
        }
    }

    // 2. Redirect to Dashboard if already logged in
    if (pathname === '/') {
        if (authSession) {
            return NextResponse.redirect(new URL('/dashboard', request.url));
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         * - env-config.js (legacy config, though we removed it)
         */
        '/((?!api|_next/static|_next/image|favicon.ico).*)',
    ],
};
