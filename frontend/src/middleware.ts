import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const authSession = request.cookies.get('auth_session');
    const profileComplete = request.cookies.get('profile_complete');
    const { pathname } = request.nextUrl;

    let response: NextResponse;

    // 1. Dashboard - requires auth AND complete profile
    if (pathname.startsWith('/dashboard')) {
        if (!authSession) {
            response = NextResponse.redirect(new URL('/', request.url));
        } else if (profileComplete?.value !== '1') {
            response = NextResponse.redirect(new URL('/onboarding', request.url));
        } else {
            response = NextResponse.next();
        }
    }
    // 2. Onboarding - requires auth, blocks if profile already complete
    else if (pathname === '/onboarding') {
        if (!authSession) {
            response = NextResponse.redirect(new URL('/', request.url));
        } else if (profileComplete?.value === '1') {
            response = NextResponse.redirect(new URL('/dashboard', request.url));
        } else {
            response = NextResponse.next();
        }
    }
    // 3. Landing - redirect if fully authenticated
    else if (pathname === '/') {
        if (authSession && profileComplete?.value === '1') {
            response = NextResponse.redirect(new URL('/dashboard', request.url));
        } else {
            response = NextResponse.next();
        }
    }
    // 4. Admin - requires auth (profile check optional based on policy)
    else if (pathname.startsWith('/admin')) {
        if (!authSession) {
            response = NextResponse.redirect(new URL('/', request.url));
        } else {
            response = NextResponse.next();
        }
    }
    else {
        response = NextResponse.next();
    }

    // Set Cross-Origin headers to allow Firebase Auth popups
    response.headers.set('Cross-Origin-Opener-Policy', 'unsafe-none');
    response.headers.delete('Cross-Origin-Embedder-Policy');

    return response;
}

export const config = {
    matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
