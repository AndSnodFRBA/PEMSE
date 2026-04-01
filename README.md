# Panhandle EMS Education — Student Portal

Full-stack Django web portal for PEMSE student registration, document management, handbook signing, and enrollment tracking.

**Stack:** Django 4.2 · PostgreSQL (Railway) · AWS S3 (file storage) · WhiteNoise (static files) · Gunicorn · GitHub Actions CI/CD

---

## Project Structure

```
pemse/
├── pemse/               # Django project config (settings, urls, wsgi)
├── students/            # Auth, dashboard, registration form, payment contract
├── courses/             # Course catalog, enrollment
├── documents/           # File uploads → AWS S3
├── handbook/            # Student handbook chapters + digital signature
├── templates/           # All HTML templates
├── static/css/          # portal.css — full portal styles
├── manage.py
├── requirements.txt
├── Procfile             # gunicorn start command
├── railway.toml         # Railway deploy config
└── .env.example         # Copy to .env for local dev
```

---

## Local Development Setup

### 1. Clone and open in VS Code
```bash
git clone https://github.com/YOUR_ORG/pemse-portal.git
cd pemse-portal
code pemse.code-workspace
```

### 2. Create virtual environment
```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your actual values
```

Add this to your `pemse/settings.py` top (already included):
```python
from dotenv import load_dotenv
load_dotenv()
```

Or just export variables in your terminal:
```bash
export SECRET_KEY="your-dev-secret-key"
export DEBUG=True
```

### 5. Run migrations and seed data
```bash
python manage.py migrate
python manage.py seed_courses       # Seeds all 7 PEMSE 2025 courses
python manage.py seed_handbook      # Seeds 7 handbook chapters
python manage.py seed_documents     # Seeds 4 document types
python manage.py createsuperuser    # Create admin login
```

### 6. Run the development server
```bash
python manage.py runserver
```

Visit: http://localhost:8000

Admin panel: http://localhost:8000/admin

---

## AWS S3 Setup (Document Storage)

### 1. Create an S3 Bucket
1. Go to AWS Console → S3 → **Create bucket**
2. Name: `pemse-documents`
3. Region: `us-east-1` (or your preferred region)
4. **Block all public access** — keep this ON (documents are private, served via signed URLs)
5. Enable versioning (optional but recommended)

### 2. Create an IAM User
1. Go to IAM → Users → **Add users**
2. Name: `pemse-s3-user`
3. Attach policy: **AmazonS3FullAccess** (or create a scoped policy below)
4. Download the Access Key ID and Secret Access Key

**Scoped IAM policy (recommended):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::pemse-documents/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::pemse-documents"
    }
  ]
}
```

### 3. Add CORS Configuration to bucket
Go to your bucket → Permissions → CORS:
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedOrigins": ["https://your-railway-domain.up.railway.app"],
    "ExposeHeaders": ["ETag"]
  }
]
```

### 4. Set environment variables
```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=pemse-documents
AWS_S3_REGION_NAME=us-east-1
```

---

## Railway Deployment

### 1. Create a Railway account
Sign up at https://railway.app and install the Railway CLI:
```bash
npm install -g @railway/cli
railway login
```

### 2. Create a new project
```bash
railway init
# Select "Empty project"
```

### 3. Add PostgreSQL
In the Railway dashboard:
- Click **+ New** → **Database** → **PostgreSQL**
- Railway automatically injects `DATABASE_URL` into your service

### 4. Set environment variables in Railway
Go to your service → **Variables** tab and add:
```
SECRET_KEY          = <generate a long random string>
DEBUG               = False
ALLOWED_HOSTS       = your-app.up.railway.app
AWS_ACCESS_KEY_ID   = ...
AWS_SECRET_ACCESS_KEY = ...
AWS_STORAGE_BUCKET_NAME = pemse-documents
AWS_S3_REGION_NAME  = us-east-1
EMAIL_BACKEND       = django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST_USER     = ems.edu911@gmail.com
EMAIL_HOST_PASSWORD = <gmail-app-password>
```

Generate a strong SECRET_KEY:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Connect GitHub repo and deploy
```bash
railway link          # link to your Railway project
railway up            # manual deploy
```

Or connect your GitHub repo in the Railway dashboard for automatic deploys on every push to `main`.

### 6. Run seed commands on Railway (first deploy only)
```bash
railway run python manage.py seed_courses
railway run python manage.py seed_handbook
railway run python manage.py seed_documents
railway run python manage.py createsuperuser
```

---

## GitHub Actions CI/CD

The workflow at `.github/workflows/deploy.yml`:
1. Runs Django tests on every push and pull request
2. Auto-deploys to Railway on every merge to `main`

**Required GitHub Secrets** (Settings → Secrets → Actions):
```
RAILWAY_TOKEN    # From Railway dashboard → Account → Tokens
```

---

## Django Admin

The admin panel at `/admin/` gives Robin and Andrew full control:

| Section | What you can do |
|---|---|
| **Students** | View all registrations, enrollment status, signatures, confirm numbers |
| **Course Enrollments** | See which students enrolled in which course |
| **Courses** | Update pricing, descriptions, add/remove courses |
| **Document Types** | Manage required document list |
| **Student Documents** | Review uploads, approve or reject with notes |
| **Handbook Chapters** | Edit handbook content — changes are live immediately |
| **Announcements** | Post updates visible on every student dashboard |
| **Payment Records** | View payment method and dept billing info |

---

## Key URLs

| URL | Page |
|---|---|
| `/` | Redirect → dashboard (if logged in) or login |
| `/login/` | Student login |
| `/register/` | Create new student account |
| `/dashboard/` | Student dashboard with checklist |
| `/register/form/` | 4-section registration form + payment contract |
| `/courses/` | Course information and enrollment |
| `/handbook/` | Student handbook with digital signature |
| `/documents/` | Document upload center |
| `/profile/` | Edit personal info |
| `/admin/` | Django admin (staff only) |

---

## Adding Features Later

**Email notifications** — `students/views.py` has a `# TODO: send_registration_email(student)` comment. Implement with Django's `send_mail()` using the EMAIL_* settings already configured.

**Student status updates** — Admins can change `enroll_status` in the admin panel. Add email triggers on status change using Django signals in `students/models.py`.

**Payment tracking** — Add a `Payment` model with amount/date/receipt fields and link it to `PaymentRecord`.

**PDF generation** — Add `reportlab` or `weasyprint` to generate a printable registration confirmation PDF on submission.
