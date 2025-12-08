import '@testing-library/jest-dom'
import { TextEncoder, TextDecoder } from 'util'

// Mock environment variables for tests
process.env.API_URL = process.env.API_URL || 'https://api.test.local';

// Mock Next.js router
jest.mock('next/navigation', () => require('next-router-mock'))

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
    motion: {
        div: ({ children, ...props }) => require('react').createElement('div', props, children),
        main: ({ children, ...props }) => require('react').createElement('main', props, children),
    },
    AnimatePresence: ({ children }) => children,
}))

// Mock react-markdown (ESM-only module that Jest cannot parse)
jest.mock('react-markdown', () => {
    return function ReactMarkdown({ children }) {
        return require('react').createElement('div', { 'data-testid': 'markdown' }, children);
    };
})

global.TextEncoder = TextEncoder
global.TextDecoder = TextDecoder

// Mock document.hidden for visibility API tests
Object.defineProperty(document, 'hidden', {
    writable: true,
    value: false,
});

global.fetch = jest.fn(() =>
    Promise.resolve({
        json: () => Promise.resolve({}),
    })
)

global.Response = class Response {
    constructor(body, init) {
        this.body = body
        this.status = init?.status || 200
        this.ok = this.status >= 200 && this.status < 300
    }
    json() { return Promise.resolve({}) }
}

global.Request = class Request { }
global.Headers = class Headers { }
