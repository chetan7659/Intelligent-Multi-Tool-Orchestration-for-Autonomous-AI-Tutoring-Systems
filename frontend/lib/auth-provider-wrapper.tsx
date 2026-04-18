'use client'

import { AuthProvider } from '@/lib/auth-context'
import type { ReactNode } from 'react'

/**
 * Client component wrapper for AuthProvider.
 * Needed because Next.js `layout.tsx` is a Server Component
 * and cannot directly render client-only providers.
 */
export function AuthProviderWrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}
