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

## Page Wireframe Descriptions

### 1. Landing / Home

- Hero section with event banner image
- "Browse Events" CTA button
- Featured events carousel (3–4 cards)
- Footer with links

### 2. Event Listing

- Search/filter bar (date, name)
- Event cards in a responsive grid (image, name, date, venue, price range)
- Pagination controls
- Each card links to Event Detail

### 3. Event Detail

- Event banner image + info (name, date, venue, hall)
- Pricing tier legend (e.g., CAT1 = $350, CAT2 = $200)
- "Select Seats" button → navigates to Seat Selection

### 4–5. Login / Register

- Centered card form
- Email + password fields (Register adds: phone, confirm password)
- Error messages inline
- Link to toggle between Login ↔ Register

### 6. Seat Selection

- Interactive seat grid (rows A–D, numbered seats)
- Color-coded: Available (green), Held (yellow), Sold (grey)
- Click available seat → "Reserve" button appears with price
- On reserve: 5-minute countdown timer starts
- "Proceed to Checkout" button

### 7. Checkout

- Order summary card: event name, seat (Row B, Seat 12), price
- Current credit balance shown
- If balance < price: "Top Up Credits" link
- "Pay with Credits" button
- OTP modal (appears only for high-risk/flagged users): 6-digit input + submit
- Success state → "View Ticket" button

### 8. My Tickets

- List/grid of owned tickets
- Each card: event name, date, venue, row/seat number, "SOLD" badge
- "Show QR" button on each card
- "Transfer" button on each card
- Empty state: "No tickets yet — browse events"

### 9. Ticket Detail / QR

- Large QR code (center of screen)
- Auto-refresh countdown: "QR refreshes in 47s"
- Event name, date, row/seat info below QR
- "Back to My Tickets" link
- QR auto-refreshes by calling `GET /api/tickets/:seatId/qr` every 50 seconds

### 10–11. Transfer Flow

- **Initiate page:** Form with buyer email/user ID, credit amount, seat info shown
- **Confirm page:** Two OTP input fields (seller + buyer), "Confirm Transfer" button
- Success state: "Transfer complete! Ticket now belongs to [buyer]"
- Error states: wrong OTP, max retries, insufficient credits

### 12. Credit Top-up

- Current balance displayed prominently
- Amount input (predefined buttons: $50, $100, $200, custom)
- Stripe Elements card form (or redirect to Stripe Checkout)
- On success: balance updates in real-time

### 13. Profile

- Read-only display: email, phone, credit balance
- Risk status indicator (if flagged)
- Logout button

---

## Component Inventory

| Component | Used On | Notes |
|---|---|---|
| `Navbar` | All pages | Logo, nav links, login/logout, credit balance badge |
| `EventCard` | Event Listing, Home | Reusable event summary card |
| `SeatGrid` | Seat Selection | Interactive grid with click handlers |
| `QRDisplay` | Ticket Detail | QR renderer + auto-refresh timer |
| `OTPModal` | Checkout, Transfer Confirm | 6-digit code input with retry counter |
| `CreditBadge` | Navbar, Checkout, Profile | Shows current credit balance |
| `CountdownTimer` | Seat Selection, QR Display | Visual countdown (5 min hold / 60s QR) |
| `StripeForm` | Credit Top-up | Stripe Elements integration |
| `Toast/Alert` | Global | Success/error notifications |
| `LoadingSpinner` | Global | For async API calls |

---

## API Integration Map

| Page | API Calls |
|---|---|
| Event Listing | `GET /api/events` |
| Event Detail | `GET /api/events/:eventId` |
| Login | `POST /api/auth/login` |
| Register | `POST /api/auth/register` |
| Seat Selection | `POST /api/reserve` |
| Checkout | `POST /api/pay`, `POST /api/verify-otp` (if flagged) |
| My Tickets | `GET /api/tickets` |
| QR Display | `GET /api/tickets/:seatId/qr` (poll every 50s) |
| Transfer Initiate | `POST /api/transfer/initiate` |
| Transfer Confirm | `POST /api/transfer/confirm` |
| Credit Top-up | `POST /api/credits/topup` |
| Profile | `GET /api/credits/balance` |

---

## Tech Stack (Recommended)

| Layer | Choice | Why |
|---|---|---|
| Framework | **Vue 3** (Composition API) | Course requirement / team familiarity |
| Router | Vue Router | SPA navigation |
| State | Pinia | Lightweight store for auth, credits, tickets |
| HTTP | Axios | Request interceptors for JWT auto-attach |
| QR Rendering | `qrcode` npm package | Renders encrypted payload as scannable QR |
| Payments | Stripe.js / Stripe Elements | PCI-compliant credit card form |
| Styling | TBD (user will decide) | Color palette, theme, fonts to be added later |

---

## Auth Flow (JWT)

```
Login → receives { access_token (15min), refresh_token (7 days) }
       → store in memory (access) + httpOnly cookie or localStorage (refresh)
       → Axios interceptor attaches "Authorization: Bearer <access_token>"
       → On 401: call POST /api/auth/refresh → get new access_token
       → On refresh failure: redirect to /login
```

---

## Notes

- **Color palette, theme, fonts, animations** — to be added later per user preference
- **OutSystems QR Scanner** — separate app, not part of this Vue SPA (see `outsystems/README.md`)
- **All API calls go through Kong** at `http://localhost:8000` (dev) or production domain
- **No direct service-to-service calls from frontend** — everything goes via the Orchestrator
