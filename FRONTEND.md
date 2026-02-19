# TicketRemaster — Frontend Blueprint

> Vue 3 SPA that talks exclusively to the backend via Kong API Gateway (`localhost:8000`).
> Staff verification uses OutSystems (separate app — see `outsystems/README.md`).

---

## Pages & Routes

### Public (no login required)

| # | Page | Route | Purpose |
|---|---|---|---|
| 1 | **Landing / Home** | `/` | Hero banner, featured events, CTA to browse |
| 2 | **Event Listing** | `/events` | Paginated grid/list of all events. Filter by date. |
| 3 | **Event Detail** | `/events/:eventId` | Event info, hall map, seat grid showing availability |
| 4 | **Login** | `/login` | Email + password form |
| 5 | **Register** | `/register` | Email, phone, password form → auto-login on success |

### Authenticated (JWT required)

| # | Page | Route | Purpose |
|---|---|---|---|
| 6 | **Seat Selection** | `/events/:eventId/seats` | Interactive seat map. Click seat → reserve (5 min hold). |
| 7 | **Checkout** | `/checkout/:orderId` | Shows held seat, price, credit balance. Pay button. OTP modal if high-risk. |
| 8 | **My Tickets** | `/tickets` | List of owned tickets with event name, date, row/seat. Each has "Show QR" button. |
| 9 | **Ticket Detail / QR** | `/tickets/:seatId` | Full-screen QR code that auto-refreshes every 50 seconds. Countdown timer. |
| 10 | **Transfer Initiate** | `/tickets/:seatId/transfer` | Enter buyer email/ID, set credit amount. Starts OTP flow for both parties. |
| 11 | **Transfer Confirm** | `/transfer/:transferId` | Both parties enter OTP codes. On success → shows "Transfer Complete". |
| 12 | **Credit Top-up** | `/credits/topup` | Enter amount → Stripe Checkout / Stripe Elements. Shows current balance. |
| 13 | **Profile** | `/profile` | View email, phone, credit balance. Flagged status (read-only). |

### Staff (OutSystems — separate app)

| # | Page | Purpose |
|---|---|---|
| S1 | **QR Scanner** | Camera-based QR scan → calls `POST /api/verify` → shows result (✅/❌) |

---

## Page Details & API Integration

> Base URL for all calls: `http://localhost:8000` (Kong gateway)
> All authenticated endpoints need header: `Authorization: Bearer <access_token>`

---

### 1. Landing / Home (`/`)

**UI:** Hero banner, featured events carousel (3–4 cards), "Browse Events" CTA, footer.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load featured events | `GET /api/events?per_page=4` | — | `data[].event_id`, `name`, `event_date`, `venue.name`, `pricing_tiers` |

---

### 2. Event Listing (`/events`)

**UI:** Search/filter bar, event card grid, pagination controls. Each card links to `/events/:eventId`.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load events | `GET /api/events?page=1&per_page=20` | Query params | `data[]` → EventCard props. `pagination.total_pages` → pagination controls |

**Error handling:** No special errors — just show empty state if `data` is empty.

---

### 3. Event Detail (`/events/:eventId`)

**UI:** Event banner, info (name, date, venue, hall), pricing legend, seat grid (from `seats` array), "Select Seats" button.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load event + seats | `GET /api/events/{event_id}` | Path param | `data.name`, `event_date`, `venue`, `pricing_tiers`, `seats[]` (status, row, seat_number, category, price) |

**Seat grid colors:** Map `seats[].status` → color:

- `AVAILABLE` → green
- `HELD` → yellow
- `SOLD` / `CHECKED_IN` → grey (disabled)

**Errors:** `EVENT_NOT_FOUND` (404) → show "Event not found" page.

---

### 4. Login (`/login`)

**UI:** Centered card, email + password inputs, submit button, link to `/register`.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Submit login | `POST /api/auth/login` | `{ "email": "...", "password": "..." }` | `data.access_token` → store in Pinia, `data.refresh_token` → localStorage, `data.user` → store user info |

**On success:** Redirect to `/events` (or previous page).
**Errors:**

- `UNAUTHORIZED` (401) → show "Invalid email or password"
- `VALIDATION_ERROR` (400) → show inline field errors

---

### 5. Register (`/register`)

**UI:** Centered card, email + phone + password + confirm password, submit button, link to `/login`.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Submit register | `POST /api/auth/register` | `{ "email": "...", "phone": "+65...", "password": "..." }` | `data.user_id`, `data.message` |

**On success:** Auto-login by calling `POST /api/auth/login` immediately, then redirect to `/events`.
**Errors:**

- `EMAIL_ALREADY_EXISTS` (409) → "This email is already registered"
- `VALIDATION_ERROR` (400) → inline field errors (email format, phone format, password too short)

---

### 6. Seat Selection (`/events/:eventId/seats`) 🔒

**UI:** Interactive seat grid, click to select, "Reserve" button, 5-minute countdown timer on reserve.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Load seats | `GET /api/events/{event_id}` | Path param | `data.seats[]` → render grid |
| Reserve seat (click) | `POST /api/reserve` | `{ "seat_id": "...", "user_id": "..." }` | `data.order_id` (save for checkout), `data.held_until`, `data.ttl_seconds` → start countdown |

**On reserve success:** Start 5-minute countdown → show "Proceed to Checkout" button → navigate to `/checkout/:orderId`.
**Errors:**

- `SEAT_UNAVAILABLE` (409) → toast "This seat is held by someone else. Try another."
- `SEAT_ALREADY_SOLD` (409) → toast "This seat is already sold." + refresh grid
- `EVENT_ENDED` (410) → toast "This event has ended."

---

### 7. Checkout (`/checkout/:orderId`) 🔒

**UI:** Order summary (event, seat, price), credit balance display, "Pay with Credits" button. OTP modal if flagged.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Load balance | `GET /api/credits/balance` | — | `data.credit_balance` → display |
| Pay | `POST /api/pay` | `{ "order_id": "..." }` | `data.status` → if `CONFIRMED`, show success! `data.credits_charged`, `data.remaining_balance` |
| OTP verify (if flagged) | `POST /api/verify-otp` | `{ "user_id": "...", "otp_code": "123456", "context": "purchase", "reference_id": "<order_id>" }` | `data.verified` → if true, call `/api/pay` again |

**Flow:**

1. User clicks "Pay" → call `POST /api/pay`
2. If response is `OTP_REQUIRED` (428): show OTP modal → user enters 6-digit code → call `POST /api/verify-otp` → on success, call `POST /api/pay` again
3. If response is `CONFIRMED`: show success → "View Ticket" button → navigate to `/tickets`

**Errors:**

- `HOLD_EXPIRED` (410) → "Your hold expired. Please re-select your seat." → redirect to `/events/:eventId/seats`
- `INSUFFICIENT_CREDITS` (402) → "Not enough credits." → show "Top Up" link → `/credits/topup`
- `OTP_INVALID` (401) → "Wrong OTP code, try again" (keep modal open)
- `OTP_MAX_RETRIES` (429) → "Too many attempts. Please re-reserve your seat."

---

### 8. My Tickets (`/tickets`) 🔒

**UI:** Grid/list of owned tickets. Each card has event info + "Show QR" and "Transfer" buttons. Empty state if none.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load tickets | `GET /api/tickets` | — | `data[]` → each ticket: `seat_id`, `event.name`, `event.event_date`, `row_number`, `seat_number`, `status` |

**Card actions:**

- "Show QR" → navigate to `/tickets/:seatId`
- "Transfer" → navigate to `/tickets/:seatId/transfer`

---

### 9. Ticket Detail / QR (`/tickets/:seatId`) 🔒

**UI:** Large QR code, auto-refresh countdown ("QR refreshes in 47s"), event info below QR.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Get QR (on load + every 50s) | `GET /api/tickets/{seat_id}/qr` | Path param | `data.qr_payload` → render as QR image, `data.ttl_seconds` → start countdown |

**Implementation:**

```js
// In setup()
const { data } = await api.get(`/api/tickets/${seatId}/qr`)
qrPayload.value = data.data.qr_payload

// Auto-refresh every 50 seconds
useIntervalFn(async () => {
  const { data } = await api.get(`/api/tickets/${seatId}/qr`)
  qrPayload.value = data.data.qr_payload
  countdown.value = 50
}, 50000)
```

**Errors:**

- `NOT_SEAT_OWNER` (403) → "You don't own this ticket"
- `SEAT_NOT_FOUND` (404) → "Ticket not found"

---

### 10. Transfer Initiate (`/tickets/:seatId/transfer`) 🔒

**UI:** Form with buyer email/user ID input, credit amount input, seat info display. "Start Transfer" button.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Submit transfer | `POST /api/transfer/initiate` | `{ "seat_id": "...", "seller_user_id": "...", "buyer_user_id": "...", "credits_amount": 300.00 }` | `data.transfer_id` (save for confirm page), `data.status` ("PENDING_OTP") |

**On success:** Navigate to `/transfer/:transferId`.
**Errors:**

- `NOT_SEAT_OWNER` (403) → "You don't own this ticket"
- `INSUFFICIENT_CREDITS` (402) → "Buyer doesn't have enough credits"
- `TRANSFER_IN_PROGRESS` (409) → "A transfer is already pending for this ticket"
- `SELF_TRANSFER` (400) → "You can't transfer to yourself"
- `USER_NOT_FOUND` (404) → "Buyer not found"

---

### 11. Transfer Confirm (`/transfer/:transferId`) 🔒

**UI:** Two OTP input fields (seller OTP + buyer OTP), "Confirm Transfer" button. Status display.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Submit OTPs | `POST /api/transfer/confirm` | `{ "transfer_id": "...", "seller_otp": "123456", "buyer_otp": "654321" }` | `data.status` ("COMPLETED"), `data.new_owner_user_id`, `data.credits_transferred` |

**On success:** Show "Transfer complete! Ticket now belongs to [buyer]" → "Back to My Tickets" button.
**Errors:**

- `OTP_INVALID` (401) → "One or both OTP codes are wrong. Try again."
- `OTP_EXPIRED` (410) → "OTP expired. Please re-initiate the transfer."
- `OTP_MAX_RETRIES` (429) → "Too many attempts. Transfer cancelled."
- `TRANSFER_INVALID_STATE` (409) → "This transfer is no longer active."

---

### 12. Credit Top-up (`/credits/topup`) 🔒

**UI:** Current balance display, amount selector ($50/$100/$200/custom), Stripe card form, "Pay" button.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Load balance | `GET /api/credits/balance` | — | `data.credit_balance` |
| Create payment | `POST /api/credits/topup` | `{ "amount": 100.00 }` | `data.client_secret` → pass to Stripe.js `confirmCardPayment()` |
| After Stripe success | `GET /api/credits/balance` | — | Refresh `data.credit_balance` display |

**Stripe.js flow:**

```js
import { loadStripe } from '@stripe/stripe-js'

const stripe = await loadStripe('pk_test_...')
const { data } = await api.post('/api/credits/topup', { amount: 100 })

// Use Stripe Elements to collect card → confirmCardPayment
const result = await stripe.confirmCardPayment(data.data.client_secret, {
  payment_method: { card: cardElement }
})
if (result.paymentIntent.status === 'succeeded') {
  // Stripe webhook will add credits server-side
  // Refresh balance after a short delay
  setTimeout(() => refreshBalance(), 2000)
}
```

**Errors:**

- `VALIDATION_ERROR` (400) → "Amount must be positive"

---

### 13. Profile (`/profile`) 🔒

**UI:** Read-only display of user info, credit balance, flagged status. Logout button.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load balance | `GET /api/credits/balance` | — | `data.credit_balance` |
| Logout | `POST /api/auth/logout` | — | Clear Pinia store + localStorage → redirect to `/login` |

---

### Global: Navbar Component

| Action | API Call | When |
|---|---|---|
| Check auth state | — | Read from Pinia `authStore.isLoggedIn` |
| Show credit balance | `GET /api/credits/balance` | On login, on route change (debounced) |
| Refresh token | `POST /api/auth/refresh` | Axios interceptor handles this automatically on 401 |

---

### Global: 401 Token Refresh (Axios Interceptor)

| Trigger | API Call | Request | Action |
|---|---|---|---|
| Any API returns 401 | `POST /api/auth/refresh` | Header: `Authorization: Bearer <refresh_token>` | Store new `access_token` → retry original request. If refresh also fails → redirect to `/login` |

---

## Tech Stack

### Core (team choice)

| Layer | Choice | Why |
|---|---|---|
| Framework | **Vue 3** (Composition API + `<script setup>`) | Team choice. Use Composition API — it's cleaner than Options API for new projects |
| Build Tool | **Vite** | Default for Vue 3. Near-instant hot-reload (<100ms). `npm create vue@latest` uses Vite |
| Router | **Vue Router 4** | SPA navigation, route guards for auth-protected pages |
| State | **Pinia** | Official Vue 3 store. Simple API for auth state, credit balance, ticket lists |
| HTTP | **Axios** | Request interceptors to auto-attach JWT and auto-refresh on 401 |
| Styling | **Tailwind CSS v3** | Utility-first CSS — style directly in templates. Massive speed-up vs writing custom CSS |
| Language | **JavaScript** (not TypeScript) | Simpler for the team. Can upgrade later if needed |

### Recommended Libraries

| Library | npm install | Purpose |
|---|---|---|
| `vue-qrcode` | `npm i @chenfengyuan/vue-qrcode` | Renders QR codes as a `<vue-qrcode>` component |
| `@stripe/stripe-js` | `npm i @stripe/stripe-js` | Stripe Elements for credit card form (PCI-compliant) |
| `vue-toastification` | `npm i vue-toastification` | Toast notifications (success/error popups) |
| `@heroicons/vue` | `npm i @heroicons/vue` | 300+ free icons as Vue components |
| `@vueuse/core` | `npm i @vueuse/core` | Utility composables — useInterval (QR timer), useLocalStorage, etc. |
| `dayjs` | `npm i dayjs` | Lightweight date formatting (event dates, countdowns) |

### Project Scaffold Command

```bash
npm create vue@latest ticketremaster-frontend
# Options to select:
#   ✔ Add Vue Router? → Yes
#   ✔ Add Pinia? → Yes
#   ✔ Add ESLint? → Yes
#   ✔ Add Prettier? → Yes
#   Everything else → No

cd ticketremaster-frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install axios vue-toastification @chenfengyuan/vue-qrcode @heroicons/vue @vueuse/core dayjs @stripe/stripe-js
```

### Tailwind CSS Setup (after scaffold)

Add the Tailwind Vite plugin in `vite.config.js`:

```js
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
})
```

Add to your main CSS file (e.g. `src/assets/main.css`):

```css
@import "tailwindcss";
```

---

## Auth Flow (JWT)

```text
Login → receives { access_token (15min), refresh_token (7 days) }
       → store access_token in Pinia (memory) — lost on refresh
       → store refresh_token in localStorage
       → Axios interceptor attaches "Authorization: Bearer <access_token>"
       → On 401: call POST /api/auth/refresh → get new access_token
       → On refresh failure: clear store → redirect to /login
```

### Axios Setup (recommended pattern)

```js
// src/api/client.js
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',  // Kong gateway
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      const refreshed = await auth.refresh()
      if (refreshed) {
        error.config.headers.Authorization = `Bearer ${auth.accessToken}`
        return api.request(error.config)
      }
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default api
```

---

## Folder Structure (recommended)

```
src/
├── api/
│   └── client.js          # Axios instance + interceptors
├── assets/
│   └── main.css           # Tailwind imports
├── components/
│   ├── Navbar.vue
│   ├── EventCard.vue
│   ├── SeatGrid.vue
│   ├── QRDisplay.vue
│   ├── OTPModal.vue
│   ├── CreditBadge.vue
│   ├── CountdownTimer.vue
│   ├── StripeForm.vue
│   └── Toast.vue
├── views/                 # One file per page/route
│   ├── HomeView.vue
│   ├── EventListView.vue
│   ├── EventDetailView.vue
│   ├── LoginView.vue
│   ├── RegisterView.vue
│   ├── SeatSelectionView.vue
│   ├── CheckoutView.vue
│   ├── MyTicketsView.vue
│   ├── TicketQRView.vue
│   ├── TransferInitiateView.vue
│   ├── TransferConfirmView.vue
│   ├── CreditTopupView.vue
│   └── ProfileView.vue
├── stores/
│   ├── auth.js            # login, logout, refresh, user info
│   ├── tickets.js         # owned tickets
│   └── credits.js         # balance
├── router/
│   └── index.js           # route definitions + auth guards
├── App.vue
└── main.js
```

---

## Notes

- **Color palette, theme, fonts** — to be added later per team preference (Tailwind makes this easy to swap via `tailwind.config.js`)
- **OutSystems QR Scanner** — separate app, not part of this Vue SPA (see `outsystems/README.md`)
- **All API calls go through Kong** at `http://localhost:8000` (dev) or production domain
- **No direct service-to-service calls from frontend** — everything goes through the Orchestrator
- **Tailwind CSS v3 docs** — <https://tailwindcss.com/docs>
