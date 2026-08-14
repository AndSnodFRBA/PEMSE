# PEMSE Portal — Demo Instance Setup

This is a sales-demo deployment of the PEMSE portal — same codebase, separate
Railway project, separate database, generic branding, and fictional sample
data. It's used to show prospective EMS training agencies what the product
looks like without touching the real Panhandle EMS Education site or data.

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
| AGENCY_ADDRESS | Your Agency Address Here |
| AGENCY_PHONE | Your Phone Number |
| AGENCY_EMAIL | your@email.com |
| AGENCY_DIRECTOR | Agency Director |
| AGENCY_TAGLINE | EMS Training Portal — Student Portal |
| AGENCY_NAVY | #2B5EA7 |
| AGENCY_ACCENT | #5B9BC8 |
| ALLOWED_HOSTS | your-demo-app.up.railway.app |
| CSRF_TRUSTED_ORIGINS | https://your-demo-app.up.railway.app |
| DATABASE_URL | (auto-injected by Railway PostgreSQL) |

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
| Staff | director@demo-ems.com | demo1234 |
| Instructor | instructor@demo-ems.com | demo1234 |
| Student | james.anderson@demo-ems.com | demo1234 |

Seven other demo students exist, all following the pattern
`firstname.lastname@demo-ems.com` with the same password.

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
