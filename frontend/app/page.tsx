// Root "/" is handled by middleware.ts which redirects to /chat or /signin
// This page is never actually rendered but must exist
export default function RootPage() {
  return null
}
