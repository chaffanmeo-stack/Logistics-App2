-- ============================================================
-- Courier & Logistics Tracking System — fresh schema
-- Run this in the Supabase SQL Editor. This DROPS old tables first.
-- ============================================================

drop table if exists cod_clearances cascade;
drop table if exists packages cascade;
drop table if exists trips cascade;
drop table if exists profiles cascade;

create extension if not exists pgcrypto;

-- ------------------------------------------------------------
-- profiles: every login (Owner, Hub, Rider, Customer) lives here.
-- Owner/Hub  -> email + password_hash
-- Rider/Customer -> phone + pin_hash
-- All hashes are bcrypt (via pgcrypto's crypt() here, or passlib
-- in the app — both produce the same bcrypt format).
-- ------------------------------------------------------------
create table profiles (
  id uuid primary key default gen_random_uuid(),
  role text not null check (role in ('Owner', 'Hub', 'Rider', 'Customer')),
  full_name text not null default '',

  email text unique,
  password_hash text,

  phone text unique,
  pin_hash text,

  home_hub text check (home_hub in ('BWP', 'Multan', 'Lahore', 'Lodhran', 'RYK')),

  -- Rider only: running COD cash total currently held, uncleared
  cod_collected numeric not null default 0,

  created_at timestamptz not null default now(),

  constraint profiles_identity_check check (
    (role in ('Owner', 'Hub') and email is not null)
    or
    (role in ('Rider', 'Customer') and phone is not null)
  )
);

create index idx_profiles_phone on profiles (phone);
create index idx_profiles_email on profiles (email);
create index idx_profiles_role on profiles (role);

-- ------------------------------------------------------------
-- trips: one vehicle's journey through a route of hubs.
-- Position is never stored directly — it's always calculated from
-- started_at + minutes_per_leg, so it's always "live" when read.
-- ------------------------------------------------------------
create table trips (
  id uuid primary key default gen_random_uuid(),
  origin_hub text not null check (origin_hub in ('BWP', 'Multan', 'Lahore', 'Lodhran', 'RYK')),
  route jsonb not null,  -- ordered array of hub codes after origin, e.g. ["Multan","Lodhran","RYK"]
  minutes_per_leg numeric not null default 90,
  current_leg_index int not null default 0,  -- how many legs fully completed so far
  status text not null default 'In Progress' check (status in ('In Progress', 'Completed')),
  started_at timestamptz not null default now(),
  created_by uuid references profiles(id),
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- packages
-- ------------------------------------------------------------
create table packages (
  id uuid primary key default gen_random_uuid(),
  tracking_id text unique not null,

  sender_name text not null,
  receiver_name text not null,
  receiver_phone text not null,
  receiver_email text,
  receiver_address text,

  origin_hub text not null check (origin_hub in ('BWP', 'Multan', 'Lahore', 'Lodhran', 'RYK')),
  destination_hub text not null check (destination_hub in ('BWP', 'Multan', 'Lahore', 'Lodhran', 'RYK')),

  -- Where the package physically is right now, when not on a trip.
  -- Null while In Transit (it's on a vehicle, not sitting at a hub).
  current_hub text check (current_hub in ('BWP', 'Multan', 'Lahore', 'Lodhran', 'RYK')),

  weight_kg numeric not null default 0,
  distance_km numeric not null default 0,
  length_cm numeric not null default 0,
  width_cm numeric not null default 0,
  height_cm numeric not null default 0,
  fare_pkr numeric not null default 0,       -- delivery/service charge
  cod_amount numeric not null default 0,     -- item value the Rider collects on delivery

  status text not null default 'Booked'
    check (status in ('Booked', 'In Transit', 'Reached Hub', 'Out for Delivery', 'Delivered', 'Cancelled')),

  trip_id uuid references trips(id),
  assigned_rider_id uuid references profiles(id),
  delivery_code text,  -- shown to Customer, entered by Rider to prove delivery
  delivered_at timestamptz,

  created_by uuid references profiles(id),
  created_at timestamptz not null default now()
);

create index idx_packages_receiver_phone on packages (receiver_phone);
create index idx_packages_tracking_id on packages (tracking_id);
create index idx_packages_current_hub on packages (current_hub);
create index idx_packages_trip_id on packages (trip_id);
create index idx_packages_assigned_rider on packages (assigned_rider_id);

-- ------------------------------------------------------------
-- cod_clearances: audit trail each time a Rider's collected cash
-- is handed in and reset at a hub.
-- ------------------------------------------------------------
create table cod_clearances (
  id uuid primary key default gen_random_uuid(),
  rider_id uuid not null references profiles(id),
  amount numeric not null,
  cleared_by uuid references profiles(id),
  cleared_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- Row Level Security — locked down to the service_role key only.
-- The app enforces who-sees-what in its own code (session role),
-- same approach as before.
-- ------------------------------------------------------------
alter table profiles enable row level security;
alter table trips enable row level security;
alter table packages enable row level security;
alter table cod_clearances enable row level security;

-- ------------------------------------------------------------
-- Seed the one Owner account. Password below is: Owner@12345
-- CHANGE THIS before sharing the app with anyone — update it by
-- running:
--   update profiles set password_hash = crypt('your-new-password', gen_salt('bf'))
--   where role = 'Owner';
-- ------------------------------------------------------------
insert into profiles (role, full_name, email, password_hash)
values (
  'Owner',
  'Affan',
  'Itsfani992@gmail.com',
  crypt('Owner@12345', gen_salt('bf'))
);
