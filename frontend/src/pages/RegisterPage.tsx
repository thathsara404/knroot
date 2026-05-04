import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export function RegisterPage() {
  const [form, setForm] = useState({
    full_name: '',
    username: '',
    email: '',
    phone: '',
    password: '',
    confirm_password: '',
  })
  const [clientError, setClientError] = useState<string | null>(null)
  const { isLoading, error, fieldErrors, signUp } = useAuth()

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setClientError(null)

    if (form.password !== form.confirm_password) {
      setClientError('Passwords do not match')
      return
    }

    const payload = {
      full_name: form.full_name,
      username: form.username,
      email: form.email,
      password: form.password,
      ...(form.phone ? { phone: form.phone } : {}),
    }
    await signUp(payload)
  }

  function fieldErr(name: string) {
    return fieldErrors?.[name]
      ? <p className="text-red-400 text-xs mt-1">{fieldErrors[name]}</p>
      : null
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-zinc-100">Create your account</h1>
          <p className="text-zinc-400 text-sm mt-1">Knowledge Root</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            { id: 'full_name', label: 'Full name', type: 'text', autoComplete: 'name', required: true },
            { id: 'username', label: 'Username', type: 'text', autoComplete: 'username', required: true },
            { id: 'email', label: 'Email', type: 'email', autoComplete: 'email', required: true },
            { id: 'phone', label: 'Phone (optional)', type: 'tel', autoComplete: 'tel', required: false },
            { id: 'password', label: 'Password', type: 'password', autoComplete: 'new-password', required: true },
            { id: 'confirm_password', label: 'Confirm password', type: 'password', autoComplete: 'new-password', required: true },
          ].map(({ id, label, type, autoComplete, required }) => (
            <div key={id}>
              <label className="block text-sm text-zinc-300 mb-1.5">{label}</label>
              <input
                type={type}
                value={form[id as keyof typeof form]}
                onChange={set(id)}
                required={required}
                autoComplete={autoComplete}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2.5 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
              />
              {fieldErr(id)}
            </div>
          ))}

          {(clientError || error) && (
            <p className="text-red-400 text-sm">{clientError ?? error}</p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-zinc-100 text-zinc-900 font-medium rounded-lg py-2.5 text-sm hover:bg-white disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="text-center text-zinc-500 text-sm mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-zinc-300 hover:text-zinc-100">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
