'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react'
import { createClient } from '@/lib/supabase/client'
import type { User, Session } from '@supabase/supabase-js'

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuthContextValue {
  /** The currently authenticated user, or null if not signed in */
  user: User | null
  /** The current Supabase session */
  session: Session | null
  /** Whether the initial auth check has completed */
  isLoading: boolean
  /**
   * Get the current access token (JWT).
   * Automatically refreshes expired tokens.
   * Returns null if not authenticated.
   */
  getToken: () => Promise<string | null>
  /** Sign out and clear session */
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const supabase = useMemo(() => createClient(), [])
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Initial session check + auth state listener
  useEffect(() => {
    // Get current session on mount
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s)
      setUser(s?.user ?? null)
      setIsLoading(false)
    })

    // Listen for auth state changes (login, logout, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s)
      setUser(s?.user ?? null)
      setIsLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [supabase])

  // Get current JWT — refreshes if expired
  const getToken = useCallback(async (): Promise<string | null> => {
    const { data: { session: s } } = await supabase.auth.getSession()
    return s?.access_token ?? null
  }, [supabase])

  // Sign out
  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    setUser(null)
    setSession(null)
  }, [supabase])

  const value = useMemo<AuthContextValue>(
    () => ({ user, session, isLoading, getToken, signOut }),
    [user, session, isLoading, getToken, signOut]
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Access the authenticated user, session, and auth utilities.
 * Must be used inside an `<AuthProvider>`.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an <AuthProvider>')
  }
  return ctx
}
