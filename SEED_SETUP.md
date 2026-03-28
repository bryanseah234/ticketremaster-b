# Database Seed Setup

## Prerequisites
- Docker Desktop installed and running
- You are in the root of the project directory (`ticketremaster-b/`)

---

## Step 1 — Build and start all containers fresh

```powershell
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

> Wait about **30 seconds** for all services and databases to finish initialising before proceeding.

---

## Step 2 — Copy seed files into containers

```powershell
docker cp venue-service/seed_venues.py ticketremaster-venue-service-1:/app/seed_venues.py
docker cp event-service/seed_events.py ticketremaster-event-service-1:/app/seed_events.py
docker cp seat-service/seed_seats.py ticketremaster-seat-service-1:/app/seed_seats.py
docker cp seat-inventory-service/seed_seat_inventory.py ticketremaster-seat-inventory-service-1:/app/seed_seat_inventory.py
```

---

## Step 3 — Run seeds in order

```powershell
docker exec -it ticketremaster-venue-service-1 python seed_venues.py
docker exec -it ticketremaster-event-service-1 python seed_events.py
docker exec -it ticketremaster-seat-service-1 python seed_seats.py
docker exec -it ticketremaster-seat-inventory-service-1 python seed_seat_inventory.py
```

Each command should print something like `Seed complete. Created X record(s).`

---

## Notes
- **Order matters** — do not skip or reorder Step 3
- **Re-running is safe** — seeds skip existing records, so you can run them again without duplicates
- If a container name differs, run `docker ps` to find the exact name and substitute accordingly
