import '@testing-library/jest-dom'
import { TextEncoder, TextDecoder } from 'util'

global.TextEncoder = TextEncoder
global.TextDecoder = TextDecoder

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
