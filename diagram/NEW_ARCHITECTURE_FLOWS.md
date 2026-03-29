# System Architecture Diagrams - Modern Infrastructure

## Infrastructure Components
- **Cloudflare**: DDoS protection, CDN, WAF
- **Kong API Gateway**: Rate limiting, authentication, routing
- **Kubernetes (K8s)**: Container orchestration
- **Redis**: Caching, session management, distributed locks
- **PostgreSQL**: Primary database
- **RabbitMQ**: Message queue with DLX
- **gRPC**: High-performance service communication
- **Stripe**: Payment processing

---

## 1. Ticket Purchase Flow

### Happy Path
```mermaid
sequenceDiagram
    participant U as User
    participant CF as Cloudflare
    participant K as Kong Gateway
    participant SS as Seat Service
    participant R as Redis
    participant RA as Risk Assessment
    participant TF as 2FA Service
    participant P as Payment Service
    participant S as Stripe
    participant O as Order Service
    participant RMQ as RabbitMQ

    U->>CF: Select Seat
    CF->>K: Forward Request
    K->>SS: Reserve Seat (gRPC)
    SS->>R: Set Lock (5-min TTL)
    R-->>SS: Lock Confirmed
    SS-->>K: Seat Reserved
    K->>RA: Assess Risk
    RA-->>K: High Risk Detected
    K->>TF: Require 2FA
    TF->>U: Send OTP
    U->>TF: Submit OTP
    TF->>R: Verify OTP
    R-->>TF: Valid
    TF-->>K: 2FA Success
    K->>P: Process Payment
    P->>S: Charge Credit Card
    S-->>P: Payment Success
    P->>O: Create Order
    O->>R: Update Credit Balance
    O->>RMQ: Publish Order Event
    RMQ->>U: Send Confirmation
```

### Unhappy Path (Reservation Expiry)
```mermaid
sequenceDiagram
    participant SS as Seat Service
    participant R as Redis
    participant RMQ as RabbitMQ
    participant DLX as Dead Letter Exchange
    participant RS as Release Service
    participant I as Inventory Service

    SS->>R: Set Lock (5-min TTL)
    Note over R: Timer starts...
    R->>RMQ: Queue Message (TTL=5min)
    alt Payment Received
        RMQ->>RS: Cancel Release
    else Timeout
        RMQ->>DLX: Message Expired
        DLX->>RS: Trigger Release
        RS->>R: Remove Lock
        R-->>RS: Lock Removed
        RS->>I: Update Availability
        I-->>SS: Seat Available
    end
```

---

## 2. Secure Peer-to-Peer Ticket Transfer

### Happy Path
```mermaid
sequenceDiagram
    participant S as Seller
    participant B as Buyer
    participant K as Kong Gateway
    participant T as Transfer Service
    participant R as Redis
    participant TF as 2FA Service
    participant AS as Atomic Swap
    participant DB as PostgreSQL
    participant I as Inventory Service

    S->>K: Initiate Transfer (Buyer ID, Seat ID)
    K->>T: Create Transfer Request
    T->>R: Generate OTP (TTL=5min)
    T->>S: Send OTP to Seller
    T->>B: Send OTP to Buyer
    S->>TF: Verify OTP
    B->>TF: Verify OTP
    TF->>R: Validate Both OTPs
    R-->>TF: Valid
    TF-->>T: Both Authenticated
    T->>AS: Execute Atomic Swap
    par Parallel Operations
        AS->>DB: BEGIN TRANSACTION
        AS->>DB: Debit Buyer Credits
        AS->>DB: Credit Seller Credits
        AS->>DB: Update Seat Ownership
        AS->>DB: COMMIT
    and
        AS->>I: Update Inventory Record
    end
    AS-->>T: Swap Complete
    T->>S: Transfer Success
    T->>B: Transfer Success
```

### Unhappy Path (OTP Failure)
```mermaid
sequenceDiagram
    participant S as Seller
    participant B as Buyer
    participant T as Transfer Service
    participant R as Redis
    participant TF as 2FA Service

    T->>R: Generate OTP (TTL=5min)
    Note over R: Timer starts...
    alt OTP Expired
        R->>T: TTL Expired
        T->>S: Transfer Cancelled
        T->>B: Transfer Cancelled
    else OTP Mismatch
        S->>TF: Submit OTP
        TF->>R: Verify
        R-->>TF: Invalid
        TF-->>T: Verification Failed
        T->>S: Transfer Failed
        T->>B: Transfer Failed
        Note over T: No state changes (atomic guarantee)
    end
```

---

## 3. Ticket Verification (QR Scan)

### Happy Path
```mermaid
sequenceDiagram
    participant Staff as Staff Mobile
    participant CF as Cloudflare
    participant K as Kong Gateway
    participant V as Validation Service
    participant R as Redis
    participant I as Inventory Service
    participant O as Order Service
    participant E as Event Service

    Staff->>CF: Scan QR Code
    CF->>K: Forward Request
    K->>V: Validate QR
    V->>R: Acquire Scan Lock (Seat ID)
    R-->>V: Lock Acquired
    par Parallel Validation
        V->>I: Check Seat Exists & Valid
        I-->>V: Valid
        V->>O: Check Payment & Duplicate
        O-->>V: Paid & Unique
        V->>E: Check Venue & Expiry
        E-->>V: Match & Not Expired
    end
    V->>R: Mark QR as Used
    V->>R: Release Scan Lock
    V-->>Staff: Entry Granted
    V->>K: Log Successful Entry
```

### Unhappy Path (Validation Failures)
```mermaid
sequenceDiagram
    participant Staff as Staff Mobile
    participant V as Validation Service
    participant R as Redis
    participant I as Inventory Service
    participant O as Order Service
    participant E as Event Service

    Staff->>V: Scan QR
    V->>R: Acquire Scan Lock
    par Parallel Checks
        V->>I: Check Seat
        I-->>V: Exists
        V->>O: Check Duplicate
        O-->>V: Duplicate Detected
        V->>E: Check Venue
        E-->>V: Valid
    end
    alt Any Validation Fails
        V->>R: Release Lock
        V-->>Staff: Entry Denied
        Note over V: Reason: Duplicate Scan
        V->>K: Log Attempt
        V->>A: Send Alert
    end
```

---

## Infrastructure Flow Diagram

```mermaid
graph TB
    subgraph "Edge Layer"
        CF[Cloudflare<br/>DDoS/WAF/CDN]
    end

    subgraph "API Gateway"
        K[Kong<br/>Rate Limiting<br/>Auth]
    end

    subgraph "Kubernetes Cluster"
        subgraph "Microservices"
            SS[Seat Service]
            TS[Transfer Service]
            VS[Validation Service]
            PS[Payment Service]
            OS[Order Service]
            IS[Inventory Service]
            ES[Event Service]
        end

        subgraph "Data Layer"
            R[(Redis<br/>Cache/Locks)]
            DB[(PostgreSQL<br/>Primary DB)]
            RMQ[RabbitMQ<br/>Message Queue]
        end
    end

    subgraph "External Services"
        S[Stripe]
        TF[2FA Service]
    end

    User --> CF
    CF --> K
    K --> SS
    K --> TS
    K --> VS
    K --> PS

    SS <--> R
    TS <--> R
    VS <--> R
    PS <--> S
    PS <--> TF

    SS <--> DB
    OS <--> DB
    IS <--> DB
    ES <--> DB

    SS <--> RMQ
    OS <--> RMQ
    IS <--> RMQ

    style CF fill:#f96,stroke:#333
    style K fill:#9f6,stroke:#333
    style R fill:#69f,stroke:#333
    style DB fill:#6f9,stroke:#333
```

---

## Key Architecture Decisions

1. **Cloudflare First**: All traffic passes through Cloudflare for DDoS protection and WAF
2. **Kong Gateway**: Centralized API management, rate limiting, and authentication
3. **Redis for Performance**: Distributed locks, session management, caching
4. **Kubernetes Orchestration**: Scalable microservices deployment
5. **gRPC for Internal Comms**: High-performance service-to-service communication
6. **RabbitMQ DLX**: Automatic cleanup of expired reservations
7. **Atomic Operations**: Database transactions ensure data consistency
8. **Parallel Validation**: QR verification runs multiple checks simultaneously
