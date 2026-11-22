export function wsUrl(path) {
  const configured = import.meta.env.VITE_WS_BASE
  if (configured) return `${configured.replace(/\/$/, '')}${path}`
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}
