---
description: 
globs: *.js
alwaysApply: false
---
# JavaScript Coding Guidelines

*   **Modern JavaScript (ES6+):**
    *   **Principle:** Utilize modern JavaScript features for cleaner, more expressive, and maintainable code.
    *   **Application:** Prefer `let` and `const` over `var`. Use arrow functions for concise syntax, especially for callbacks. Employ template literals for string interpolation. Use classes for object-oriented patterns. Leverage destructuring assignments, spread/rest operators, and async/await for asynchronous operations.

*   **Modularity (ES Modules):**
    *   **Principle:** Organize code into reusable modules to improve structure, maintainability, and enable code splitting.
    *   **Application:** Use `import` and `export` statements to share code between files. Each module should have a single responsibility.

*   **Strict Mode:**
    *   **Principle:** Use strict mode to catch common coding bloopers and to create more robust code.
    *   **Application:** Add `'use strict';` at the beginning of your scripts or functions. This helps avoid accidental global variables and makes debugging easier.

*   **Error Handling:**
    *   **Principle:** Implement robust error handling for both synchronous and asynchronous operations.
    *   **Application:** Use `try...catch...finally` blocks for synchronous code. For Promises, use `.catch()` or `try...catch` with `async/await`. Handle errors gracefully and provide meaningful feedback or logging.

*   **Readability and Formatting:**
    *   **Principle:** Write code that is easy to read, understand, and maintain.
    *   **Application:** Follow a consistent style guide (e.g., Airbnb, StandardJS, Google). Use meaningful variable and function names. Comment complex logic, but avoid over-commenting obvious code. Use tools like ESLint and Prettier to enforce style and catch errors.

*   **DOM Manipulation:**
    *   **Principle:** Interact with the DOM efficiently and avoid performance bottlenecks.
    *   **Application:** Minimize direct DOM manipulations. Batch DOM updates if possible. Use event delegation to handle events on multiple elements efficiently. Prefer modern APIs like `document.querySelector` and `document.querySelectorAll`.

*   **Asynchronous Operations:**
    *   **Principle:** Manage asynchronous operations effectively using Promises and `async/await`.
    *   **Application:** Prefer `async/await` for cleaner asynchronous code flow. Handle Promise rejections properly. Avoid callback hell.

*   **Code Comments:**
    *   **Principle:** Use comments to explain *why* something is done, or to clarify complex or non-obvious logic, not *what* the code is doing if it's self-evident.
    *   **Application:** Document non-trivial functions, algorithms, or workarounds. Remove commented-out code before committing.

*   **Security Considerations:**
    *   **Principle:** Be mindful of common web security vulnerabilities.
    *   **Application:** Sanitize user inputs to prevent XSS attacks. Be cautious with `eval()` and `innerHTML`. When dealing with third-party libraries, keep them updated. 