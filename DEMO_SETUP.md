# PEMSE Portal — Demo Instance Setup

This is a sales-demo deployment of the PEMSE portal — same codebase, separate
Railway project, separate database, generic branding, and fictional sample
data. It's used to show prospective EMS training agencies what the product
looks like without touching the real Panhandle EMS Education site or data.

This portal is built and maintained by
[Four Line Software LLC](https://www.fourlinesoftware.com). The demo
instance's "DEMO MODE" banner and footer credit both identify Four Line
Software as the vendor — that's intentional, and separate from the
`AGENCY_*` branding, which represents whichever prospective customer is
being demoed.

## Deploy to Railway

1. Create a new Railway project
2. Connect the same GitHub repo (PEMSE)
3. Add a PostgreSQL database service
4. Set these environment variables:

| Variable | Demo Value |
|---|---|
| SECRET_KEY | (generate a new random key — never reuse the production key) |
| DEBUG | False |
| DEMO_MODE | True |
| AGENCY_NAME | EMS Training Portal |
| AGENCY_SHORT_NAME | EMS Portal |
| AGENCY_ADDRESS | 123 Main Street, Anytown, USA |
| AGENCY_PHONE | Available upon request |
| AGENCY_EMAIL | info@emstrainingportal.com |
| AGENCY_DIRECTOR | Portal Administrator |
| AGENCY_TAGLINE | EMS Training Portal — Student Management System |
| AGENCY_NAVY | #2B5EA7 |
| AGENCY_ACCENT | #5B9BC8 |
| ALLOWED_HOSTS | your-demo-app.up.railway.app |
| DATABASE_URL | (auto-injected by Railway PostgreSQL) |

These values are intentionally generic — no real agency name, city, phone
number, or person's name. Keep it that way: don't fill in a real address or
director name here, even a placeholder-sounding one, since this project's
whole purpose is to demo the product without revealing (or being confused
with) any specific customer's identity.

`SOFTWARE_COMPANY` and `SOFTWARE_COMPANY_URL` are **not** environment
variables — they're fixed in `pemse/settings.py` ("Four Line Software LLC" /
`https://www.fourlinesoftware.com`), the same on every deployment. That's
deliberate: the software vendor is the same company regardless of which
agency is being demoed, so there's nothing to configure per-deployment.
Setting them as Railway variables has no effect on the running app.

`CSRF_TRUSTED_ORIGINS` is derived automatically from `ALLOWED_HOSTS` at
startup — there's no separate variable to set.

Do **not** set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` on the demo
project — with `DEMO_MODE=True`, file uploads always use local storage
regardless, but leaving S3 credentials off entirely keeps things simple and
guarantees no demo document can ever land in the real S3 bucket.

5. After first deploy, seed the base reference data and demo data, in order:

```
railway run python manage.py seed_courses
railway run python manage.py seed_handbook
railway run python manage.py seed_documents
railway run python manage.py seed_emt_hybrid_schedule
railway run python manage.py seed_demo_data
```

(`seed_emt_hybrid_schedule` populates the calendar sessions that
`seed_demo_data` uses to generate sample attendance records — run it first,
or the demo course will show no attendance history.)

## Demo login credentials

| Role | Email | Password |
|---|---|---|
| Staff | director@emstrainingportal.com | demo1234 |
| Instructor | instructor@emstrainingportal.com | demo1234 |
| Student | james.anderson@emstrainingportal.com | demo1234 |

Seven other demo students exist, all following the pattern
`firstname.lastname@emstrainingportal.com` with the same password. Demo
students live in a rotating set of generic Nebraska cities (Norfolk,
Kearney, North Platte, Columbus, Fremont) — none of them Scottsbluff.

## Resetting demo data between demos

Log in as staff and click **Reset Demo Data** on the dashboard (only visible
when `DEMO_MODE=True`), or run:

```
railway run python manage.py reset_demo_data
```

This wipes every non-superuser account and re-seeds fresh sample data. It
refuses to run unless `DEMO_MODE=True`, so it can never be triggered against
the real production database.

## Customizing branding for a prospect

Update the `AGENCY_*` environment variables in Railway for each prospect
demo, then redeploy (or just restart the service — no code changes or
migrations are required). Branding is read from environment variables on
every request, so it updates immediately.

## What demo mode restricts

With `DEMO_MODE=True`:
- Outgoing email uses the console backend — nothing is actually sent.
- File uploads always use local disk storage, never S3.
- The daily tasks webhook (`/webhooks/daily-tasks/`) no-ops instead of
  running the real management commands.
- All generated PDFs (certificates, receipts, reports, rosters) get a
  diagonal "SAMPLE" watermark.
- A "DEMO MODE" banner appears on every page.
- `SiteSettings.get()` — the source PDFs pull agency name/address/phone/email
  /director from — returns a value built live from the `AGENCY_*` variables
  instead of the database-backed singleton, and is never persisted. This
  means changing an `AGENCY_*` variable and restarting the service is enough
  to rebrand every PDF; nobody needs to visit `/staff/settings/` on the demo
  project.

## The logo image

The `AGENCY_LOGO_URL` variable (optional) lets you swap the logo image for a
prospect. If it's left unset and `DEMO_MODE=True`, every page falls back to
generic text/icon placeholders instead of the bundled `static/images/PEMSE.jpg`
file (the real PEMSE logo), so the demo never shows that graphic.
