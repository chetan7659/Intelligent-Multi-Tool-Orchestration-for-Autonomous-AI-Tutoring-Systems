/**
 * API client — all backend requests go through here.
 *
 * Every request automatically attaches the Supabase JWT token
 * from the auth session, ensuring the backend can identify the user.
 */

import { createClient } from '@/lib/supabase/client'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string
  session_id?: string
  student_id?: string
  student_profile?: Record<string, unknown>
}

export interface ToolResult {
  tool_name: string
  success: boolean
  output: Record<string, unknown>
  confidence: number
  execution_time_ms: number
  error?: string
}

export interface ChatResponse {
  session_id: string
  message_id: string
  response: string
  tool_used?: string
  tool_result?: ToolResult
  extracted_params?: Record<string, unknown>
  confidence: number
  workflow_steps: string[]
  timestamp: string
}

export interface Tool {
  name: string
  description: string
  category: string
  required_params: string[]
  optional_params: string[]
  example_trigger_phrases: string[]
}

export interface ToolListResponse {
  total: number
  tools: Tool[]
  by_category: Record<string, string[]>
}

export interface SessionInfo {
  session_id: string
  user_id: string
  title: string | null
  primary_subject: string | null
  message_count: number
  tools_used: string[]
  created_at: string
  updated_at: string
}

export interface UserProfile {
  user_id: string
  email: string
  full_name: string | null
  learning_level: string
  total_sessions: number
  total_messages: number
  token_balance: number
  streak_days: number
}

// ─── Token helper ─────────────────────────────────────────────────────────────

/**
 * Get the current JWT access token from Supabase auth.
 * Returns null if not authenticated.
 */
async function getAccessToken(): Promise<string | null> {
  try {
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token ?? null
  } catch {
    return null
  }
}

// ─── Core fetch wrapper ───────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAccessToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  }

  // Attach JWT if available — backend uses this to identify the user
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }

  return res.json() as Promise<T>
}

// ─── API functions ────────────────────────────────────────────────────────────

/**
 * Send a chat message. JWT is attached automatically.
 * The backend extracts user_id from the token and links everything.
 */
export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

/** List available tools (public endpoint, no auth needed) */
export async function listTools(): Promise<ToolListResponse> {
  return apiFetch<ToolListResponse>('/tools')
}

/** Health check (public endpoint) */
export async function healthCheck(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/health')
}

/** Create a new conversation session */
export async function createSession(): Promise<SessionInfo> {
  return apiFetch<SessionInfo>('/sessions', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

/** List the current user's sessions */
export async function listSessions(): Promise<{ sessions: SessionInfo[] }> {
  return apiFetch<{ sessions: SessionInfo[] }>('/sessions')
}

/** Get a specific session with its messages */
export async function getSession(sessionId: string): Promise<any> {
  return apiFetch<any>(`/sessions/${sessionId}`)
}

/** Get the current user's profile (requires auth) */
export async function getProfile(): Promise<UserProfile> {
  return apiFetch<UserProfile>('/me')
}
