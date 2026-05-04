import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { RegisterPage } from './RegisterPage'

const mockHook = {
  isLoading: false,
  error: null as string | null,
  fieldErrors: null as Record<string, string> | null,
  signUp: vi.fn(),
}

vi.mock('../hooks/useAuth', () => ({ useAuth: () => mockHook }))

const VALID_FORM = {
  full_name: 'Alice Tester',
  username: 'alicetester',
  email: 'alice@example.com',
  password: 'SecurePass1',
  confirm_password: 'SecurePass1',
}

async function fillAndSubmit(overrides: Partial<typeof VALID_FORM> = {}) {
  const values = { ...VALID_FORM, ...overrides }
  const user = userEvent.setup()

  await user.type(screen.getByLabelText(/full name/i), values.full_name)
  await user.type(screen.getByLabelText(/^username/i), values.username)
  await user.type(screen.getByLabelText(/^email/i), values.email)
  await user.type(screen.getByLabelText(/^password$/i), values.password)
  await user.type(screen.getByLabelText(/confirm password/i), values.confirm_password)
  await user.click(screen.getByRole('button', { name: /create account/i }))
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockHook.isLoading = false
  mockHook.error = null
  mockHook.fieldErrors = null
  mockHook.signUp = vi.fn()
})

describe('RegisterPage', () => {
  it('renders all required fields', () => {
    renderPage()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
  })

  it('calls signUp with correct payload on valid submit', async () => {
    mockHook.signUp.mockResolvedValue(undefined)
    renderPage()

    await fillAndSubmit()

    await waitFor(() =>
      expect(mockHook.signUp).toHaveBeenCalledWith({
        full_name: 'Alice Tester',
        username: 'alicetester',
        email: 'alice@example.com',
        password: 'SecurePass1',
      })
    )
  })

  it('shows client-side error when passwords do not match', async () => {
    renderPage()
    await fillAndSubmit({ confirm_password: 'Different1' })

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    expect(mockHook.signUp).not.toHaveBeenCalled()
  })

  it('shows server error message', () => {
    mockHook.error = 'Email already in use'
    renderPage()
    expect(screen.getByText('Email already in use')).toBeInTheDocument()
  })

  it('shows per-field validation errors from server', () => {
    mockHook.fieldErrors = { username: 'Username is too short' }
    renderPage()
    expect(screen.getByText('Username is too short')).toBeInTheDocument()
  })

  it('disables button and shows loading text while submitting', () => {
    mockHook.isLoading = true
    renderPage()
    const btn = screen.getByRole('button', { name: /creating account/i })
    expect(btn).toBeDisabled()
  })

  it('has a link back to the login page', () => {
    renderPage()
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login')
  })

  it('omits phone from payload when left blank', async () => {
    mockHook.signUp.mockResolvedValue(undefined)
    renderPage()
    await fillAndSubmit()

    await waitFor(() => {
      const payload = mockHook.signUp.mock.calls[0][0]
      expect(payload).not.toHaveProperty('phone')
    })
  })
})
