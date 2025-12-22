// A hook to lock a function until the previous promise is resolved
// @param fn - The function to lock
// @returns The locked function
// export function useLockFn<P extends any[] = any[], V = any>(
// fn: (...args: P) => Promise<V>,
// ): (...args: P) => Promise<V | undefined>

import { useCallback, useRef } from 'react'

export function useLockFn<P extends any[] = any[], V = any>(
  fn: (...args: P) => Promise<V>,
) {
  const lockRef = useRef(false)

  return useCallback(
    async (...args: P) => {
      if (lockRef.current) {
        return
      }

      lockRef.current = true

      try {
        return await fn(...args)
      } finally {
        lockRef.current = false
      }
    },
    [fn],
  )
}
