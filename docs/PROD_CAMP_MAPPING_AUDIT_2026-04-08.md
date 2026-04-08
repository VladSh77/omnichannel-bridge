# Production Camp Mapping Audit (2026-04-08)

## Environment Audited

- Host: `91.98.122.195` (SSH read-only session)
- Odoo DB: `campscout`
- Container: `campscout_web`
- Addons paths observed:
  - `/opt/campscout/custom-addons/campscout_management`
  - `/opt/campscout/addons/bs_campscout_addon`
  - `/opt/campscout/custom-addons/omnichannel_bridge`

## Confirmed Models/Fields (Runtime)

- `discuss.channel` exists, `mail.channel` does not exist (important for omnichannel bridge inheritance).
- `product.template` fields confirmed:
  - `bs_event_id`
  - `bs_seats_available`
  - `omni_places_remaining`
- `product.product` fields confirmed:
  - `bs_event_id`
  - `bs_seats_available`
  - `omni_places_remaining`
- `event.event` fields confirmed:
  - `seats_available`
  - `seats_reserved`
  - `seats_used`
  - `registration_ids`
- `event.registration.state` exists with states in production:
  - `open`, `done`, `draft`, `cancel`

## Confirmed Seat Logic in Server Code

1. `campscout_management/models/product_template.py`
   - `get_camp_availability()`:
     - collects `event.event.ticket` by product variants,
     - maps to future events,
     - returns `sum(events.seats_available)`.

2. `bs_campscout_addon/models/product.py`
   - `bs_event_id` on both template and variant.
   - `bs_seats_available` is related to `bs_event_id.seats_available`.

3. `bs_campscout_addon/models/event_event.py`
   - `_compute_seats`:
     - counts registrations by state (`open` -> reserved, `done` -> used),
     - computes `seats_available` from `seats_max`,
     - subtracts seats from confirmed sales lines via `get_seats_quantity_from_sales()`.
   - this means availability is impacted by both registrations and sale lines.

## Production Data Spot Checks

- Sample camp products show `bs_event_id` actively used for core programs.
- Sample events:
  - event `59`: `seats_available=14`, states `{open: 1}`
  - event `60`: `seats_available=37`, states `{open: 3}`
  - event `61`: `seats_available=18`, states `{open: 12, cancel: 3}`
  - event `67`: `seats_available=30`, states `{}`

## Mapping Decision for `omnichannel_bridge`

Priority order for places remains valid and production-aligned:

1. `product.template.get_camp_availability()`
2. `product.template/product.product.bs_event_id.seats_available`
3. `event.event.ticket` -> `event.event.seats_available`
4. fallback to `omni_places_remaining`

## Risks Found

- Server deployment path currently is not git-backed (`/opt/campscout/custom-addons/omnichannel_bridge` has no `.git`).
- This breaks strict `git pull` deployment workflow until repo checkout is restored.

## Result

- TZ item "prod audit of places mapping against real DB/custom modules" is completed for read-only verification.
