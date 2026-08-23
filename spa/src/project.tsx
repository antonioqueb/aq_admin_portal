import { useEffect, useState } from 'react'

export interface ActiveProject { id: number; name: string }
const KEY = 'aq_active_project'
export const getActiveProject = (): ActiveProject | null => { try { return JSON.parse(localStorage.getItem(KEY) || 'null') } catch { return null } }
export const setActiveProject = (p: ActiveProject | null) => { if (p) localStorage.setItem(KEY, JSON.stringify(p)); else localStorage.removeItem(KEY); window.dispatchEvent(new Event('aq:project')) }
/** Hook: proyecto activo global (null = todos los proyectos). */
export function useActiveProject() {
  const [p, setP] = useState<ActiveProject | null>(getActiveProject())
  useEffect(() => { const h = () => setP(getActiveProject()); window.addEventListener('aq:project', h); return () => window.removeEventListener('aq:project', h) }, [])
  return p
}
