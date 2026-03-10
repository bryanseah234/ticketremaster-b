# TicketRemaster — Frontend Blueprint & Integration Guide

> Vue 3 SPA that talks natively to the backend via Nginx API Gateway.
> Staff verification uses OutSystems (separate app — see `outsystems/README.md`).

---

## Environment & Base URL

Your frontend is deployed at `https://ticketremaster.hong-yi.me` (or `ticketremaster.vercel.app`). The API Gateway is configured to accept CORS requests from these origins.

All API requests **must** prefix the paths shown below with your server's API URL (e.g., `https://your-api-domain.com/api`).
For local development, use: `http://localhost:8000/api`

Use a Vite env var and read it in your API client:

- Local dev: `VITE_API_BASE_URL=http://localhost:8000/api`
- Production (Vercel): `VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me/api`

If your backend only runs locally, use Cloudflare Tunnel for a stable public URL.

**Cloudflare Tunnel (recommended):**

1. Add a domain to Cloudflare and ensure DNS is active.
2. Cloudflare Zero Trust → Access → Tunnels → Create Tunnel.
3. Copy the tunnel token and set `CLOUDFLARE_TUNNEL_TOKEN` in your environment.
4. Add a Public Hostname pointing to:
   - Docker compose: `http://api-gateway:8000`
   - Local host (no Docker): `http://localhost:8000`
5. Set `VITE_API_BASE_URL=https://ticketremasterapi.hong-yi.me/api` in Vercel.

> **Do not communicate directly with microservices (port 5000, 5002, etc.). Always go through the gateway on port 8000.**

---

## Pages & Routes (Required for Frontend Developers / Agents)

Your frontend must implement these core views.

### Public (no login required)

| # | Page | Route | Purpose |
|---|---|---|---|
| 1 | **Landing / Home** | `/` | Hero banner, featured events, CTA to browse |
| 2 | **Event Listing** | `/events` | Paginated grid/list of all events. Filter by date. |
| 3 | **Event Detail** | `/events/:eventId` | Event info, hall map, seat grid showing availability |
| 4 | **Login** | `/login` | Email + password form |
| 5 | **Register** | `/register` | Email, phone, password form → redirects to OTP page |
| 5.5 | **Verify OTP** | `/verify` | Enter SMS OTP sent during registration → auto-login on success |

### Authenticated (JWT required)

| # | Page | Route | Purpose |
|---|---|---|---|
| 6 | **Seat Selection** | `/events/:eventId/seats` | Interactive seat map. Click seat → reserve (5 min hold). |
| 7 | **Checkout** | `/checkout/:orderId` | Shows held seat, price, credit balance. Pay button. OTP modal if high-risk. |
| 8 | **My Tickets** | `/tickets` | List of owned tickets. Each has "Show QR" and "Transfer" buttons. |
| 9 | **Ticket Detail / QR** | `/tickets/:seatId` | Full-screen QR code auto-refreshes every 50 seconds. Countdown timer. |
| 10 | **Transfer Initiate** | `/tickets/:seatId/transfer` | Enter buyer email/ID, credit amount. Starts OTP flow for both parties. |
| 11 | **Transfer Confirm** | `/transfer/:transferId` | Both parties enter OTP codes. On success → shows "Transfer Complete". |
| 12 | **Credit Top-up** | `/credits/topup` | Enter amount → Stripe Checkout / Stripe Elements. Shows current balance. |
| 13 | **Profile & Favourites** | `/profile` | View email, phone, credit balance. Flagged status (read-only). |
| 13.5| **Marketplace** | `/marketplace` | Browse tickets listed for resale. **Must include:**<br/>1. "How the Resale Marketplace Works" (Browse, Review, Purchase)<br/>2. "Why Buy From Our Marketplace" (Verified Sellers, Buyer Guarantee side-panel). |

### Administrator (Requires JWT with `is_admin` claim)

| # | Page | Route | Purpose |
|---|---|---|---|
| 14 | **Admin Event Create** | `/admin/events/new` | Form to create a new event (name, venue, pricing) and automatically bulk-provision seats. |
| 15 | **Admin Event Dashboard** | `/admin/events/:eventId/dashboard` | Real-time overview of ticket inventory, seats available, and gross sales. |

### Staff (OutSystems — separate app)

| # | Page | Purpose |
|---|---|---|
| S1 | **QR Scanner** | Camera-based QR scan → calls `POST /api/verify` → shows result (✅/❌) |

---

## Page Details & API Integration

> Base URL for all calls: `import.meta.env.VITE_API_BASE_URL`
> All authenticated endpoints need header: `Authorization: Bearer <access_token>`

### 1. Landing / Home (`/`)

**UI:** Hero banner, featured events carousel (3–4 cards), "Browse Events" CTA, footer.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load featured events | `GET /events?per_page=4` | — | `data[].event_id`, `name`, `event_date`, `venue.name`, `pricing_tiers` |

**Response fields (event list item):**

- `event_id` (string, UUID)
- `name` (string)
- `venue` (object): `venue_id` (string, UUID), `name` (string), `address` (string), `total_halls` (number)
- `hall_id` (string)
- `event_date` (string, ISO 8601)
- `total_seats` (number)
- `pricing_tiers` (object: `{ "CAT1": number, "CAT2": number, ... }`)

---

### 2. Event Listing (`/events`)

**UI:** Search/filter bar, event card grid, pagination controls. Each card links to `/events/:eventId`.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load events | `GET /events?page=1&per_page=20` | Query params | `data[]` → EventCard props. `pagination.total_pages` → pagination controls |

**Response fields:**

- `data[]` items use the same event fields listed above
- `pagination.page` (number), `pagination.per_page` (number), `pagination.total` (number), `pagination.total_pages` (number)

**Error handling:** No special errors — just show empty state if `data` is empty.

> **Globe UI & Locations Note:**
> When the frontend calls `GET /events` to populate the Event Listing page, the backend automatically attaches the `venue` object to every single event in the array.
> Your frontend agent can simply extract the `venue.address` and `venue.name` from that payload, and use those precise strings to pin the locations on your Globe UI.
> Since we want to optimize network requests, we intentionally do not have a standalone `/venues` API. Extracting it from the event list is a standard approach that saves a network call!

---

### 3. Event Detail (`/events/:eventId`)

**UI:** Event banner, info (name, date, venue, hall), pricing legend, seat grid (from `seats` array), "Select Seats" button.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load event + seats | `GET /events/{event_id}` | Path param | `data.name`, `event_date`, `venue`, `pricing_tiers`, `seats[]` (see fields below) |

**Response fields (event detail):**

- `event_id` (string, UUID)
- `name` (string)
- `venue` (object): `venue_id` (string, UUID), `name` (string), `address` (string), `total_halls` (number)
- `hall_id` (string)
- `event_date` (string, ISO 8601)
- `total_seats` (number)
- `pricing_tiers` (object: `{ "CAT1": number, "CAT2": number, ... }`)
- `seat_selection_mode` (string: `SEATMAP` | `CATEGORY`)
- `seat_config` (object, optional: `{ "category_rows": { "CAT1": ["1","2"], "CAT2": ["3","4"] } }`)
- `seats[]` (array of seat objects):
  - `seat_id` (string, UUID)
  - `event_id` (string, UUID)
  - `owner_user_id` (string, UUID or null)
  - `status` (string: `AVAILABLE` | `HELD` | `SOLD` | `CHECKED_IN` | `LISTED`)
  - `held_by_user_id` (string, UUID or null)
  - `held_until` (string, ISO 8601 or null)
  - `row_number` (string)
  - `seat_number` (number)
  - `category` (string or null)
  - `price` (number or null)
  - `price_paid` (number or null)

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
| Submit login | `POST /auth/login` | `{ "email": "user@example.com", "password": "password123" }` | `access_token`, `refresh_token`, `user` |

**Response fields (success):**

- `message` (string)
- `access_token` (string)
- `refresh_token` (string)
- `user` (object): `user_id` (string, UUID), `email` (string), `phone` (string or null), `credit_balance` (number), `is_flagged` (boolean), `is_admin` (boolean), `is_verified` (boolean)

**On success:** Redirect to `/events` (or previous page).
**Errors:**

- `UNAUTHORIZED` (401) → show "Invalid email or password"
- `UNVERIFIED_ACCOUNT` (403) → show "Please verify your phone number" and redirect to `/verify`
- `VALIDATION_ERROR` (400) → show inline field errors

---

### 5. Register (`/register`)

**UI:** Centered card, email + phone + password + confirm password, submit button, link to `/login`.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Submit register | `POST /auth/register` | `{ "email": "user@example.com", "phone": "+6591234567", "password": "password123" }` | `user_id`, `status` |

**Response fields (success):**

- `message` (string)
- `status` (string: `PENDING_VERIFICATION`)
- `user_id` (string, UUID)

**On success:** Redirect to `/verify` to prompt for OTP code. Store `user_id` to pass to the next screen. Do NOT auto-login yet.
**Errors:**

- `EMAIL_ALREADY_EXISTS` (409) → "This email is already registered"
- `VALIDATION_ERROR` (400) → inline field errors

---

### 5.5 Verify Registration (`/verify`)

**UI:** OTP 6-digit input field, submit button.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Submit OTP | `POST /auth/verify-registration` | `{ "user_id": "uuid", "otp_code": "123456" }` | `access_token`, `refresh_token`, `user` |

**Response fields (success):**

- `message` (string)
- `access_token` (string)
- `refresh_token` (string)
- `user` (object): `user_id` (string, UUID), `email` (string), `phone` (string or null), `credit_balance` (number), `is_flagged` (boolean), `is_admin` (boolean), `is_verified` (boolean)

**On success:** User is officially verified and logged in. Redirect to `/events`.
**Errors:**

- `BAD_REQUEST` (400) → "Invalid OTP code" or "No pending OTP verification found"

---

### 6. Seat Selection (`/events/:eventId/seats`) 🔒

**UI:** Interactive seat grid, click to select, "Reserve" button, 5-minute countdown timer on reserve.

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Load seats | `GET /events/{event_id}` | Path param | `data.seats[]` → render grid |
| Reserve seat (click) | `POST /reserve` | `{ "seat_id": "uuid", "event_id": "uuid" }` | `data.order_id`, `data.seat_id`, `data.status`, `data.held_until`, `data.ttl_seconds` |

**Response fields (reserve success):**

- `data.order_id` (string, UUID)
- `data.seat_id` (string, UUID)
- `data.status` (string: `HELD`)
- `data.held_until` (string, ISO 8601)
- `data.ttl_seconds` (number)

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
| Load balance | `GET /users/{user_id}` | Path param | `credit_balance` → display |
| Pay | `POST /pay` | `{ "order_id": "..." }` | `data.status` → if `CONFIRMED`, show success! `data.credits_charged`, `data.remaining_balance` |
| OTP verify (if flagged) | `POST /verify-otp` | `{ "user_id": "uuid", "otp_code": "123456", "context": "purchase", "reference_id": "order_id" }` | `message` (string) |

**Response fields (user profile):**

- `user_id` (string, UUID)
- `email` (string)
- `phone` (string or null)
- `credit_balance` (number)
- `is_flagged` (boolean)
- `is_admin` (boolean)
- `is_verified` (boolean)

**Flow:**

1. User clicks "Pay" → call `POST /pay`
2. If response is `OTP_REQUIRED` (428): show OTP modal → user enters 6-digit code → call `POST /verify-otp` → on success, call `POST /pay` again
3. If response is `CONFIRMED`: show success → "View Ticket" button → navigate to `/tickets`

**Errors:**

- `HOLD_EXPIRED` (410) → "Your hold expired. Please re-select your seat." → redirect to `/events/:eventId/seats`
- `INSUFFICIENT_CREDITS` (402) → "Not enough credits." → show "Top Up" link → `/credits/topup`
- `OTP_INVALID` (401) → "Wrong OTP code, try again" (keep modal open)
- `OTP_MAX_RETRIES` (429) → "Too many attempts. Please re-reserve your seat."

---

### 8. My Tickets (`/tickets`) 🔒

**UI:** Grid/list of owned tickets. Each card has ticket info + "Show QR" and "Transfer" buttons. Empty state if none.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load tickets | `GET /tickets` | — | `data[]` → each ticket: `seat_id`, `status`, `price_paid` |

**Response fields (ticket item):**

- `seat_id` (string, UUID)
- `status` (string: `SOLD`)
- `price_paid` (number)

**Note:** This endpoint currently does not include event metadata. If you need event name/date, add them on the backend or join by seat_id after extending the payload.

**Card actions:**

- "Show QR" → navigate to `/tickets/:seatId`
- "Transfer" → navigate to `/tickets/:seatId/transfer`

---

### 9. Ticket Detail / QR (`/tickets/:seatId`) 🔒

**UI:** Large QR code, auto-refresh countdown ("QR refreshes in 47s"), event info below QR.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Get QR (on load + every 50s) | `GET /tickets/{seat_id}/qr` | Path param | `data.qr_payload`, `data.generated_at`, `data.expires_at`, `data.ttl_seconds` |

**Response fields (QR):**

- `qr_payload` (string)
- `generated_at` (string, ISO 8601)
- `expires_at` (string, ISO 8601)
- `ttl_seconds` (number)

**Implementation:**

```js
// In setup()
const { data } = await api.get(`/tickets/${seatId}/qr`)
qrPayload.value = data.data.qr_payload

// Auto-refresh every 50 seconds
useIntervalFn(async () => {
  const { data } = await api.get(`/tickets/${seatId}/qr`)
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
| Submit transfer | `POST /transfer/initiate` | `{ "seat_id": "uuid", "seller_user_id": "uuid", "buyer_user_id": "uuid", "credits_amount": 300.00 }` | `data.transfer_id`, `data.seat_id`, `data.status`, `data.message` |

**Response fields (transfer initiate):**

- `transfer_id` (string, UUID)
- `seat_id` (string, UUID)
- `status` (string: `PENDING_OTP`)
- `message` (string)

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
| Submit OTPs | `POST /transfer/confirm` | `{ "transfer_id": "uuid", "seller_otp": "123456", "buyer_otp": "654321" }` | `data.transfer_id`, `data.status`, `data.seat_id`, `data.new_owner_user_id`, `data.credits_transferred`, `data.message` |

**Response fields (transfer confirm):**

- `transfer_id` (string, UUID)
- `status` (string: `COMPLETED`)
- `seat_id` (string, UUID)
- `new_owner_user_id` (string, UUID)
- `credits_transferred` (number)
- `message` (string)

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
| Load balance | `GET /users/{user_id}` | Path param | `credit_balance` |
| Create payment | `POST /credits/topup` | `{ "user_id": "uuid", "amount": 100.00 }` | `client_secret`, `amount`, `message` |
| After Stripe success | `GET /users/{user_id}` | Path param | Refresh `credit_balance` |

**Stripe.js flow:**

```js
import { loadStripe } from '@stripe/stripe-js'

const stripe = await loadStripe('pk_test_...')
const { data } = await api.post('/credits/topup', { user_id, amount: 100 })

// Use Stripe Elements to collect card → confirmCardPayment
const result = await stripe.confirmCardPayment(data.client_secret, {
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

---

### 12.5. Marketplace (`/marketplace`) 🔒

**UI:** A dedicated page to browse resold tickets from other users.
**Required Sections:**

1. **Hero/Header:** A clear title.
2. **Value Prop ("Why Buy From Our Marketplace?"):** A checklist showing "Verified Sellers & Ratings", "100% Buyer Protection", "Mobile Tickets Instant Delivery", "Best Price Guarantee", "No Hidden Fees", and "24/7 Customer Support", alongside a colored "Buy Confidence" guarantee card.
3. **How it Works:** A 3-step graphic (1: Browse Listings, 2: Review Details, 3: Purchase Safely).
4. **Resale Listings Grid/List:** A view showing available reseller tickets. Each card must clearly state the event name, date, row/seat number, and the seller's asking price.

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load listings | `GET /marketplace/listings?status=ACTIVE` | Query params | `listing_id`, `seat_id`, `asking_price`, `seller_user_id`, `status` |

**Response fields (listing item):**

- `listing_id` (string, UUID)
- `seat_id` (string, UUID)
- `seller_user_id` (string, UUID)
- `buyer_user_id` (string, UUID or null)
- `escrow_transaction_id` (string, UUID or null)
- `asking_price` (number)
- `status` (string: `ACTIVE` | `PENDING_TRANSFER` | `COMPLETED` | `CANCELLED`)
- `created_at` (string, ISO 8601)
- `updated_at` (string, ISO 8601)

**Marketplace Actions:**

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| List ticket | `POST /marketplace/list` | `{ "seat_id": "uuid", "asking_price": 120.00 }` | `data.listing_id`, `data.seat_id`, `data.status`, `data.message` |
| Buy listing | `POST /marketplace/buy` | `{ "listing_id": "uuid" }` | `data.listing_id`, `data.status`, `data.message` |
| Approve sale | `POST /marketplace/approve` | `{ "listing_id": "uuid", "otp_code": "123456" }` | `data.listing_id`, `data.status`, `data.message` |

**Note:** Listing responses do not include event name/date or row/seat labels. If you need these for display, the backend must be extended to enrich listings with seat/event details.

> **Terminology Note (Ticket vs. Seat):**
> In this system, **a "Ticket" and a "Seat" are the exact same thing**. A user who buys 4 tickets actually owns 4 distinct "Seats" in the database (each with its own unique `seat_id`). If they want to resell all 4, they must list each `seat_id` individually on the marketplace. There is no concept of a "batch ticket".

---

### 13. Profile & Favourites (`/profile`) 🔒

**UI:** Read-only display of user info, credit balance, flagged status. Logout button. Also a section showing "Favourited Events".

| Action | API Call | Request | Response fields to use |
|---|---|---|---|
| Load balance | `GET /users/{user_id}` | Path param | `credit_balance` |
| Logout | `POST /auth/logout` | — | Clear Pinia store + localStorage → redirect to `/login` |

**Response fields (user profile):**

- `user_id` (string, UUID)
- `email` (string)
- `phone` (string or null)
- `credit_balance` (number)
- `is_flagged` (boolean)
- `is_admin` (boolean)
- `is_verified` (boolean)

> **Note on "Favourites":** The backend database **does not** have a column to save favourited events.
> For the frontend, you must implement this feature entirely locally using `localStorage` or `sessionStorage` (e.g., using VueUse's `useLocalStorage`). When a user clicks the "Heart" icon on an event, save the `event_id` to an array in their browser.

---

### 14. Admin Functions 🔒 (Requires `is_admin: true`)

**UI:** Separate dashboard component for users with elevated privileges.

**What an Admin CAN do:**

- **Create Events:** Admins can bulk-provision thousands of seats instantly. An Event requires a Venue. The "location" is handled via the nested `venue` object (which requires a `name` and `address`).
- **View Live Dashboards:** Admins can see real-time un-cached data of how many seats are `SOLD`, `HELD` (in cart), and `AVAILABLE`.

**What an Admin CANNOT do:**

- Admins cannot manually reserve or transfer seats on behalf of a user.
- Admins cannot delete an event once tickets are sold (immutable ledger).

| Action | API Call | Request Body | Response fields to use |
|---|---|---|---|
| Admin Event Create | `POST /admin/events` | `{ "name": "...", "venue": {"name": "Test Venue", "address": "123 Test St", "total_halls": 2}, "hall_id": "HALL-1", "event_date": "2026-12-31T20:00:00", "total_seats": 250, "pricing_tiers": {"CAT1": 100}, "seat_selection_mode": "SEATMAP", "seat_config": { "category_rows": { "CAT1": ["1","2"] } } }` | `data.event_id`, `data.seats_created` |
| Admin Dashboard | `GET /admin/events/{event_id}/dashboard` | — | `data.seats_sold`, `data.seats_held`, `data.seats_available`, `data.seats_detail[]` |

**Error Handling:**
Always read the `error_code` string in the JSON response (e.g. `UNAUTHORIZED`, `FORBIDDEN`).

**Seat Selection Modes:**
- `SEATMAP` → user picks a specific seat from the map, then calls `POST /reserve` with `seat_id`.
- `CATEGORY` → user picks a category only, then call `POST /reserve-by-category` with `{ "event_id": "...", "category": "CAT1" }` to get a random available seat in that category.

---

### Global: Navbar Component

| Action | API Call | When |
|---|---|---|
| Navigation Links | — | Links to Home, Events, **Marketplace**, My Tickets, Profile |
| Check auth state | — | Read from Pinia `authStore.isLoggedIn` |
| Show credit balance | `GET /users/{user_id}` | On login, on route change (debounced) |
| Refresh token | `POST /auth/refresh` | Axios interceptor handles this automatically on 401 |

---

### Global: 401 Token Refresh (Axios Interceptor)

| Trigger | API Call | Request | Action |
|---|---|---|---|
| Any API returns 401 | `POST /auth/refresh` | Header: `Authorization: Bearer <refresh_token>` | Store new `access_token` → retry original request. If refresh also fails → redirect to `/login` |

---

### Global: API Gateway Errors (Kong)

Kong intercepts requests before your application logic. Add global interceptors or catch blocks for these:

| Error HTTP Status | Triggered By | Frontend Action / Message to Show |
|---|---|---|
| `429 Too Many Requests` | User hits the API more than 50 times in 1 minute (Rate Limit) | Show an error Toast: "You are doing that too fast. Please wait a moment before trying again." |
| `403 Forbidden` | The user is running a bot script (e.g. cURL, Python, Postman missing `User-Agent`) | Show an error Toast: "Access denied. Unusual activity detected." |

---

### Global: Tunnel Unavailable / Offline Mode

If the Cloudflare Tunnel or backend is down, the frontend should stay semi-functional with mock data and clear error states:

- Detect network failures (timeout, DNS error, `502/503/504`) and show a persistent banner: "Backend unavailable. Showing limited demo data."
- Use mock data for public pages (home, events list, event detail) so navigation still works.
- Disable checkout, seat reservation, transfer, and credit top-up flows with a clear message and disabled CTA.
- Cache the last successful event list and event detail responses in local storage and fall back to them when the backend is unreachable.
- For authenticated pages, show a "Read-only demo" state and avoid actions that mutate data.

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
npm install axios vue-toastification @chenfengyuan/vue-qrcode @heroicons/vue @vueuse/core dayjs @stripe/stripe-js
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
  baseURL: import.meta.env.VITE_API_BASE_URL,
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
    
    // Intercept Global Gateway Errors
    if (error.response?.status === 429) {
      // e.g. toast.error("You are doing that too fast. Please wait a moment before trying again.")
    } else if (error.response?.status === 403 && !error.response.data?.error_code) {
      // Kong 403s don't have our standard `{error_code: ...}` shape
      // e.g. toast.error("Access denied. Unusual activity detected.")
    }
    
    return Promise.reject(error)
  }
)

export default api
```

---

## Folder Structure (SUGGESTED)

*(Note: If you have already built views, keep what you have! This is just a suggestion for where files might live.)*

```text
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

- **OutSystems QR Scanner** — separate app, not part of this Vue SPA (see `outsystems/README.md`)
- **All API calls go through the Nginx gateway** at `http://localhost:8000/api` (dev) or via your production domain `https://ticketremasterapi.hong-yi.me/api` (prod).
- **No direct service-to-service calls from frontend** — everything goes through the Orchestrator
