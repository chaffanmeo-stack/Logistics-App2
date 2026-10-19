# RouteWise — Courier & Logistics Tracking (Streamlit)

Pure-Python GUI (Streamlit), Supabase database, simulated GPS/IoT trip
tracking, COD wallet with delivery-code proof. Free to host, no credit
card needed anywhere.

## Roles
- **Owner** — sees everything, creates Hub and Rider logins, books
  packages, dispatches trips, views all hub queues
- **Hub** — one login per physical hub (Owner creates it), scoped to
  that hub only: queue, booking, dispatching trips from that hub
- **Rider** — phone + PIN (Owner creates it), sees assigned deliveries,
  confirms delivery via a code the customer shows them, running COD
  wallet (collected / remaining)
- **Customer** — phone + PIN (auto-created the first time a package is
  booked for their number), tracks their own packages, sees the
  delivery code to hand to the rider, sees a live simulated map while
  "In Transit"

## 1. Supabase
1. Run `sql/schema.sql` in the SQL Editor. **This drops old tables** —
   only do this once you're ready to start fresh.
2. It seeds one Owner account: email as given, password `Owner@12345`.
   **Change this password** right after your first login works, by
   running in the SQL Editor:
   ```sql
   update profiles set password_hash = crypt('your-new-password', gen_salt('bf'))
   where role = 'Owner';
   ```
3. Project Settings → API → copy the Project URL and the
   **service_role** key (not anon).

## 2. Push to GitHub
Upload/replace the contents of your repo with this folder.
**Do not commit a real `.streamlit/secrets.toml`** — only
`secrets_template.toml` should go to GitHub (it has placeholder
values only).

## 3. Deploy on Streamlit Community Cloud (free, no card)
1. Go to **share.streamlit.io**, sign in with GitHub.
2. **New app** → pick your repo/branch → main file path: `app.py`.
3. Before/after deploying, open the app's **Settings → Secrets** and
   paste in (with your real values):
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "your-real-service-role-key"
   ```
4. Deploy. Future `git push`es to this repo auto-update the live app —
   no manual redeploy step.

## How the simulated GPS/IoT works
A Trip's position is never stored — it's always calculated from
`started_at` plus how many minutes you set per hub-to-hub leg. Every
time a Trip is viewed (Owner/Hub/Customer dashboards), the app
recalculates where it "should" be by now and, if it has newly crossed
into a hub, automatically:
- drops off packages destined for that hub (status → Reached Hub)
- picks up any packages already waiting at that hub for a destination
  further along the same trip's route

This is what makes the "one truck, many drop-offs and pickups along
the way" behavior work without any real hardware or background jobs.

## Folder structure
```
courier-streamlit/
├── app.py                   # entry point — routes to the right dashboard by role
├── lib/
│   ├── db.py                 # Supabase client (cached)
│   ├── security.py           # password/PIN hashing, code generators
│   ├── pricing.py            # fare calculation
│   └── simulate.py           # simulated GPS + trip auto-progress
├── views/
│   ├── login.py
│   ├── owner.py
│   ├── hub.py
│   ├── rider.py
│   ├── customer.py
│   └── shared.py             # reusable building blocks used across roles
├── sql/schema.sql
├── requirements.txt
└── .streamlit/
    ├── config.toml            # theme colors
    └── secrets_template.toml  # copy to secrets.toml locally, or paste into Cloud Secrets
```

## ⚠️ Not runtime-tested here
No internet access in my build environment to install Streamlit/Supabase
and actually run this — every file passed a Python syntax check, and I
went through the logic carefully by hand, but **please do a careful
first run yourself** and send me the exact error if anything breaks.
That's normal, especially for a build this size.
