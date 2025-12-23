import '@testing-library/jest-dom'
import { TextEncoder, TextDecoder } from 'node:util'
import React from 'react'
import nextRouterMock from 'next-router-mock'

// Mock environment variables for tests
process.env.API_URL = process.env.API_URL || 'https://api.test.local';

// Mock Next.js router
jest.mock('next/navigation', () => nextRouterMock)

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
    motion: {
        div: (props) => React.createElement('div', props),
        main: (props) => React.createElement('main', props),
    },
    AnimatePresence: ({ children }) => children,
}))

// Mock react-markdown (ESM-only module that Jest cannot parse)
jest.mock('react-markdown', () => {
    return function ReactMarkdown({ children }) {
        return React.createElement('div', { 'data-testid': 'markdown' }, children);
    };
})

globalThis.TextEncoder = TextEncoder
globalThis.TextDecoder = TextDecoder

// Mock document.hidden for visibility API tests
Object.defineProperty(document, 'hidden', {
    writable: true,
    value: false,
});

globalThis.fetch = jest.fn(() =>
    Promise.resolve({
        json: () => Promise.resolve({}),
    })
)

globalThis.Response = class Response {
    constructor(body, init) {
        this.body = body
        this.status = init?.status || 200
        this.ok = this.status >= 200 && this.status < 300
    }
    json() { return Promise.resolve({}) }
}

globalThis.Request = class Request { }
globalThis.Headers = class Headers { }
