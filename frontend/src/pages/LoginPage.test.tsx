import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { LoginPage } from './LoginPage'

const mockHook = {
  isLoading: false,
  error: null as string | null,
  fieldErrors: null as Record<string, string> | null,
  signIn: vi.fn(),
}

vi.mock('../hooks/useAuth', () => ({ useAuth: () => mockHook }))

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockHook.isLoading = false
  mockHook.error = null
  mockHook.fieldErrors = null
  mockHook.signIn = vi.fn()
})

describe('LoginPage', () => {
  it('renders identifier and password fields', () => {
    renderPage()
    expect(screen.getByLabelText(/username or email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('renders a sign-in button', () => {
    renderPage()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('calls signIn with entered values on submit', async () => {
    mockHook.signIn.mockResolvedValue(undefined)
    renderPage()
    const user = userEvent.setup()

    await user.type(screen.getByLabelText(/username or email/i), 'alice')
    await user.type(screen.getByLabelText(/password/i), 'Secret1')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() =>
      expect(mockHook.signIn).toHaveBeenCalledWith({ identifier: 'alice', password: 'Secret1' })
    )
  })

  it('shows error message from hook', () => {
    mockHook.error = 'Invalid credentials'
    renderPage()
    expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
  })

  it('disables button and shows loading text while submitting', () => {
    mockHook.isLoading = true
    renderPage()
    const btn = screen.getByRole('button', { name: /signing in/i })
    expect(btn).toBeDisabled()
  })

  it('has a link to the register page', () => {
    renderPage()
    expect(screen.getByRole('link', { name: /register/i })).toHaveAttribute('href', '/register')
  })
})
