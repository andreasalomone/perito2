import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const authSession = request.cookies.get('auth_session');
    const { pathname } = request.nextUrl;

    // Determine which response to create
    let response: NextResponse;

    // 1. Protect Dashboard Routes
    if (pathname.startsWith('/dashboard')) {
        if (!authSession) {
            response = NextResponse.redirect(new URL('/', request.url));
        } else {
            response = NextResponse.next();
        }
    }
    // 2. Redirect to Dashboard if already logged in
    else if (pathname === '/') {
        if (authSession) {
            response = NextResponse.redirect(new URL('/dashboard', request.url));
        } else {
            response = NextResponse.next();
        }
    } else {
        response = NextResponse.next();
    }

    // Set Cross-Origin headers to allow Firebase Auth popups
    // Using 'unsafe-none' for COOP allows popups from any origin (needed for Firebase)
    // Removing COEP or setting to 'unsafe-none' to avoid conflicts
    response.headers.set('Cross-Origin-Opener-Policy', 'unsafe-none');
    response.headers.delete('Cross-Origin-Embedder-Policy');

    return response;
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
