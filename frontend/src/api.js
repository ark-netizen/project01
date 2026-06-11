const BASE = import.meta.env.VITE_API_BASE ?? ''
export const api = (path) => `${BASE}${path}`
