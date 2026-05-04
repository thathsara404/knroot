import { useState, useEffect } from 'react'
import { fetchNews } from '../api/client'

export function useNews() {
  const [news, setNews] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = () => {
    setIsLoading(true)
    setError(false)
    fetchNews()
      .then(setNews)
      .catch(() => setError(true))
      .finally(() => setIsLoading(false))
  }

  useEffect(load, [])

  return { news, isLoading, error, refresh: load }
}
