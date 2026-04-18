'use client'

import { useState, useEffect, useCallback } from 'react'
import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

type AuthMode = 'signin' | 'signup' | 'forgot'

const FEATURES = [
  { icon: '🧠', title: '20 AI Tools', desc: 'Quiz, flashcards, mind maps, mock tests & more' },
  { icon: '⚡', title: 'Instant Answers', desc: 'LangGraph agents understand your exact needs' },
  { icon: '📈', title: 'Track Progress', desc: 'Personalized learning path that grows with you' },
  { icon: '🎯', title: 'Smart Routing', desc: 'Right tool selected automatically from your words' },
]

function SignInContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const supabase = createClient()

  const [mode, setMode] = useState<AuthMode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  // Pick up error from URL (e.g. OAuth failure)
  useEffect(() => {
    const urlError = searchParams.get('error')
    if (urlError) setError(decodeURIComponent(urlError))
  }, [searchParams])

  const clearMessages = () => { setError(''); setSuccess('') }

  const handleEmailAuth = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    clearMessages()

    if (!email.trim()) return setError('Email is required')
    if (mode !== 'forgot' && password.length < 6) return setError('Password must be at least 6 characters')

    setLoading(true)
    try {
      if (mode === 'forgot') {
        const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/auth/callback?next=/chat`,
        })
        if (err) throw err
        setSuccess('Check your email for a password reset link!')
        return
      }

      if (mode === 'signup') {
        const { error: err } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { full_name: fullName },
            emailRedirectTo: `${window.location.origin}/auth/callback?next=/chat`,
          },
        })
        if (err) throw err
        setSuccess('Account created! Check your email to verify, then sign in.')
        setMode('signin')
        return
      }

      // Sign in
      const { error: err } = await supabase.auth.signInWithPassword({ email, password })
      if (err) throw err
      const redirectTo = searchParams.get('redirectTo') || '/chat'
      router.push(redirectTo)
      router.refresh()

    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [mode, email, password, fullName, supabase, router, searchParams])

  const handleGoogle = useCallback(async () => {
    clearMessages()
    setGoogleLoading(true)
    try {
      const { error: err } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback?next=/chat`,
          queryParams: { access_type: 'offline', prompt: 'consent' },
        },
      })
      if (err) throw err
    } catch (err: any) {
      setError(err.message || 'Google sign in failed.')
      setGoogleLoading(false)
    }
  }, [supabase])

  const modeConfig = {
    signin: { title: 'Welcome back', subtitle: 'Sign in to continue learning', cta: 'Sign In', link: 'signup', linkText: "Don't have an account?", linkCta: 'Sign up' },
    signup: { title: 'Start learning', subtitle: 'Create your free account', cta: 'Create Account', link: 'signin', linkText: 'Already have an account?', linkCta: 'Sign in' },
    forgot: { title: 'Reset password', subtitle: "We'll send you a recovery link", cta: 'Send Reset Link', link: 'signin', linkText: 'Remembered it?', linkCta: 'Back to sign in' },
  }

  const cfg = modeConfig[mode]

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#080808', overflow: 'hidden' }}>

      {/* ── Left panel — branding ── */}
      <div style={{ width: '45%', flexShrink: 0, background: '#0a0a0a', borderRight: '1px solid #1a1a1a', display: 'flex', flexDirection: 'column', padding: '40px 48px', position: 'relative', overflow: 'hidden' }}
        className="hidden lg:flex">

        {/* Dot grid bg */}
        <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle, #1e1e1e 1px, transparent 1px)', backgroundSize: '28px 28px', opacity: 0.6 }} />

        {/* Gradient orb */}
        <div style={{ position: 'absolute', bottom: -120, left: -80, width: 400, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,201,167,0.08), transparent 70%)', filter: 'blur(40px)' }} />

        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>

          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 64 }}>
            <div style={{ width: 42, height: 42, borderRadius: 12, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#00c9a7)', padding: 2 }}>
              <div style={{ width: '100%', height: '100%', borderRadius: 10, background: '#0a0a0a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 900, color: '#fff' }}>YO</div>
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', letterSpacing: '-0.3px' }}>
                Edu<span style={{ color: '#00c9a7' }}>Orchestrator</span>
              </div>
              <div style={{ fontSize: 11, color: '#444', marginTop: 1 }}>AI powered learning, beyond Limits</div>
            </div>
          </div>

          {/* Hero text */}
          <div style={{ marginBottom: 48 }}>
            <h1 style={{ fontSize: 36, fontWeight: 700, lineHeight: 1.2, color: '#fff', marginBottom: 16 }}>
              Your personal<br />
              <span style={{ background: 'linear-gradient(135deg,#00c9a7,#0891b2)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>AI tutor</span><br />
              is waiting.
            </h1>
            <p style={{ fontSize: 15, color: '#555', lineHeight: 1.65 }}>
              Tell Yo your challenge and watch 20 specialized AI tools spring into action — automatically.
            </p>
          </div>

          {/* Features */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {FEATURES.map(f => (
              <div key={f.icon} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{ width: 38, height: 38, borderRadius: 10, background: '#111', border: '1px solid #1e1e1e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>{f.icon}</div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#e0e0e0', marginBottom: 2 }}>{f.title}</div>
                  <div style={{ fontSize: 12, color: '#555', lineHeight: 1.5 }}>{f.desc}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div style={{ marginTop: 'auto', fontSize: 12, color: '#2a2a2a' }}>
            © 2025 EduOrchestrator · Built with LangGraph + HuggingFace
          </div>
        </div>
      </div>

      {/* ── Right panel — auth form ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 24px', overflowY: 'auto' }}>

        {/* Mobile logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 40 }} className="lg:hidden">
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'conic-gradient(from 180deg,#00c9a7,#7c3aed,#ec4899,#00c9a7)', padding: 2 }}>
            <div style={{ width: '100%', height: '100%', borderRadius: 8, background: '#080808', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 900, color: '#fff' }}>YO</div>
          </div>
          <span style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>Edu<span style={{ color: '#00c9a7' }}>Orchestrator</span></span>
        </div>

        {/* Card */}
        <div style={{ width: '100%', maxWidth: 420 }}>

          {/* Heading */}
          <div style={{ marginBottom: 32, textAlign: 'center' }}>
            <h2 style={{ fontSize: 26, fontWeight: 700, color: '#fff', marginBottom: 6 }}>{cfg.title}</h2>
            <p style={{ fontSize: 14, color: '#555' }}>{cfg.subtitle}</p>
          </div>

          {/* Error / Success banners */}
          {error && (
            <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#f87171', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <span style={{ flexShrink: 0, marginTop: 1 }}>⚠️</span>
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div style={{ background: 'rgba(0,201,167,0.08)', border: '1px solid rgba(0,201,167,0.25)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#00c9a7', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <span style={{ flexShrink: 0, marginTop: 1 }}>✅</span>
              <span>{success}</span>
            </div>
          )}

          {/* Google OAuth */}
          {mode !== 'forgot' && (
            <>
              <button onClick={handleGoogle} disabled={googleLoading || loading}
                style={{ width: '100%', height: 48, background: '#111', border: '1px solid #222', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, fontSize: 14, fontWeight: 500, color: '#e0e0e0', cursor: 'pointer', transition: 'all 0.15s', marginBottom: 20 }}
                onMouseEnter={e => { if (!googleLoading) { (e.currentTarget as HTMLElement).style.background = '#161616'; (e.currentTarget as HTMLElement).style.borderColor = '#333'; } }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = '#111'; (e.currentTarget as HTMLElement).style.borderColor = '#222'; }}>
                {googleLoading ? (
                  <div style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid #333', borderTopColor: '#00c9a7', animation: 'spin 0.8s linear infinite' }} />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                )}
                Continue with Google
              </button>

              {/* Divider */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <div style={{ flex: 1, height: 1, background: '#1e1e1e' }} />
                <span style={{ fontSize: 12, color: '#444' }}>or continue with email</span>
                <div style={{ flex: 1, height: 1, background: '#1e1e1e' }} />
              </div>
            </>
          )}

          {/* Email form */}
          <form onSubmit={handleEmailAuth} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Full name (signup only) */}
            {mode === 'signup' && (
              <div>
                <label style={{ fontSize: 12, color: '#666', display: 'block', marginBottom: 6 }}>Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  placeholder="Your name"
                  autoComplete="name"
                  style={{ width: '100%', height: 46, background: '#111', border: '1px solid #222', borderRadius: 10, padding: '0 14px', fontSize: 14, color: '#e8e8e8', transition: 'border-color 0.2s', outline: 'none', fontFamily: 'inherit' }}
                  onFocus={e => { (e.target as HTMLElement).style.borderColor = '#2d6b5e'; }}
                  onBlur={e => { (e.target as HTMLElement).style.borderColor = '#222'; }}
                />
              </div>
            )}

            {/* Email */}
            <div>
              <label style={{ fontSize: 12, color: '#666', display: 'block', marginBottom: 6 }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
                style={{ width: '100%', height: 46, background: '#111', border: '1px solid #222', borderRadius: 10, padding: '0 14px', fontSize: 14, color: '#e8e8e8', transition: 'border-color 0.2s', outline: 'none', fontFamily: 'inherit' }}
                onFocus={e => { (e.target as HTMLElement).style.borderColor = '#2d6b5e'; }}
                onBlur={e => { (e.target as HTMLElement).style.borderColor = '#222'; }}
              />
            </div>

            {/* Password */}
            {mode !== 'forgot' && (
              <div>
                <label style={{ fontSize: 12, color: '#666', display: 'block', marginBottom: 6 }}>Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder={mode === 'signup' ? 'Min. 6 characters' : 'Your password'}
                    autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                    required
                    style={{ width: '100%', height: 46, background: '#111', border: '1px solid #222', borderRadius: 10, padding: '0 44px 0 14px', fontSize: 14, color: '#e8e8e8', transition: 'border-color 0.2s', outline: 'none', fontFamily: 'inherit' }}
                    onFocus={e => { (e.target as HTMLElement).style.borderColor = '#2d6b5e'; }}
                    onBlur={e => { (e.target as HTMLElement).style.borderColor = '#222'; }}
                  />
                  <button type="button" onClick={() => setShowPassword(p => !p)}
                    style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#444', padding: 4 }}>
                    {showPassword
                      ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                      : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    }
                  </button>
                </div>

                {/* Forgot password link */}
                {mode === 'signin' && (
                  <button type="button" onClick={() => { setMode('forgot'); clearMessages(); }}
                    style={{ marginTop: 6, fontSize: 12, color: '#444', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'right', width: '100%', transition: 'color 0.15s' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#00c9a7'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#444'; }}>
                    Forgot password?
                  </button>
                )}
              </div>
            )}

            {/* CTA button */}
            <button type="submit" disabled={loading || googleLoading}
              className="btn-teal"
              style={{ height: 48, borderRadius: 12, fontSize: 15, fontWeight: 600, marginTop: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              {loading ? (
                <div style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.2)', borderTopColor: '#000', animation: 'spin 0.8s linear infinite' }} />
              ) : null}
              {loading ? 'Please wait...' : cfg.cta}
            </button>
          </form>

          {/* Mode toggle */}
          <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <p style={{ fontSize: 13, color: '#555', margin: 0 }}>{cfg.linkText}</p>
            <button onClick={() => { setMode(cfg.link as AuthMode); clearMessages(); }}
              style={{
                width: '100%', height: 46, background: 'transparent',
                border: '1px solid #00c9a7', borderRadius: 12,
                color: '#00c9a7', fontSize: 14, fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s',
                fontFamily: 'inherit', display: 'flex',
                alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
              onMouseEnter={e => { const el = e.currentTarget; el.style.background = 'rgba(0,201,167,0.08)'; el.style.borderColor = '#00e6be'; }}
              onMouseLeave={e => { const el = e.currentTarget; el.style.background = 'transparent'; el.style.borderColor = '#00c9a7'; }}>
              {cfg.linkCta}
            </button>
          </div>

          {/* Terms */}
          {mode === 'signup' && (
            <p style={{ marginTop: 16, textAlign: 'center', fontSize: 11, color: '#333', lineHeight: 1.5 }}>
              By creating an account you agree to our{' '}
              <span style={{ color: '#444', textDecoration: 'underline', cursor: 'pointer' }}>Terms of Service</span>{' '}
              and{' '}
              <span style={{ color: '#444', textDecoration: 'underline', cursor: 'pointer' }}>Privacy Policy</span>
            </p>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        input:-webkit-autofill,
        input:-webkit-autofill:hover,
        input:-webkit-autofill:focus {
          -webkit-box-shadow: 0 0 0px 1000px #111 inset !important;
          -webkit-text-fill-color: #e8e8e8 !important;
          caret-color: #e8e8e8;
        }
      `}</style>
    </div>
  )
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#080808' }} />}>
      <SignInContent />
    </Suspense>
  )
}
