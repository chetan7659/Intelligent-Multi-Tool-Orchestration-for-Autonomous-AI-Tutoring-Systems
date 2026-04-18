import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { NextResponse, type NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/chat'
  const error = searchParams.get('error')
  const errorDescription = searchParams.get('error_description')

  // Handle OAuth errors
  if (error) {
    console.error('Auth callback error:', error, errorDescription)
    const url = new URL('/signin', origin)
    url.searchParams.set('error', errorDescription || error)
    return NextResponse.redirect(url)
  }

  if (code) {
    const cookieStore = await cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return cookieStore.getAll()
          },
          setAll(cookiesToSet: { name: string; value: string; options: any }[]) {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          },
        },
      }
    )

    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

    if (!exchangeError) {
      // Successful auth — redirect to intended page
      const redirectUrl = new URL(next, origin)
      return NextResponse.redirect(redirectUrl)
    }

    console.error('Session exchange error:', exchangeError)
  }

  // Something went wrong
  const url = new URL('/signin', origin)
  url.searchParams.set('error', 'Authentication failed. Please try again.')
  return NextResponse.redirect(url)
}
