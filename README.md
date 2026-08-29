# Mountaincart Timer

A single-page tool for timing mountaincart rides at Sport Klaus / Hochkönig.

## What it does
- Staff tap a cart tile to start/stop its ride timer (30 min limit, flags overtime for double-price charging)
- A manual override (clock icon) lets staff backdate a start time if they forgot to tap start
- A Settings tab lets you assign a fixed size (S / M / L / XL / V / G) to each cart
- A filter row on the Track tab shows/hides carts by size, plus a live breakdown of how many of each size are currently out
- All state is stored in Supabase (see below) so multiple devices (e.g. a tablet at the top of the hill and one at the bottom) stay in sync in real time

## Setup
This is a static single HTML file (`index.html`) with no build step — deploy it as-is to Netlify, GitHub Pages, or any static host.

It connects to a Supabase project for persistence. The Supabase URL and anon (public) key are embedded directly in `index.html` — this is safe because Row Level Security policies on the Supabase tables restrict what the anon key can do (read/write only the two tables this app uses).

### Database schema
Two tables in the connected Supabase project:
- `mountaincart_session` — single row holding cart count, live status of every cart, and each cart's size
- `mountaincart_rides` — append-only log of every completed ride (cart, start, end, duration, overtime flag)

## Deploying
Push to `main` — if this repo is linked to a Netlify site (Site configuration → Build & deploy → Link repository), it deploys automatically with no build command needed and the publish directory set to the repo root.
