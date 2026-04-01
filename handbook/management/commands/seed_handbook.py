"""python manage.py seed_handbook"""
from django.core.management.base import BaseCommand
from handbook.models import HandbookChapter

CHAPTERS = [
    (1, "Welcome & Mission", """
<p>Welcome to <strong>Panhandle EMS Education (PEMSE)</strong>, located at 709 Rosedale Dr., Scottsbluff, NE 69361.
We are dedicated to providing high-quality, hybrid EMS education to students across the Nebraska Panhandle and beyond.</p>

<h4>Our Mission</h4>
<p>To train compassionate, competent, and career-ready emergency medical professionals through rigorous hybrid
coursework, hands-on clinical experience, and dedicated instructorship.</p>

<h4>Contact Information</h4>
<p><strong>Robin Darnall</strong> — Program Director<br>
Phone: 308.631.2424 &nbsp;|&nbsp; Email: ems.edu911@gmail.com</p>
<p><strong>Andrew Snodgrass</strong> — Instructor / Co-Director<br>
Email: emseducation19@gmail.com</p>

<h4>Hybrid Course Format</h4>
<p>All PEMSE courses use a <em>hybrid model</em>, combining online coursework with in-person skills labs and
clinical rotations. Students complete online modules on their own schedule and attend all in-person sessions.</p>
"""),
    (2, "Attendance Policy", """
<h4>In-Person Sessions</h4>
<p>Attendance is mandatory for all scheduled in-person skills labs and clinical sessions.</p>

<h4>Missed Sessions</h4>
<ul>
  <li>Students who miss a skills lab must arrange a make-up session with the instructor prior to the next scheduled class.</li>
  <li>Students who miss more than 20% of scheduled in-person time may be dismissed from the program without a refund.</li>
  <li>Clinical hours missed due to illness must be documented with a physician's note and made up before the course end date.</li>
</ul>

<h4>Online Component</h4>
<p>Online modules must be completed by the deadlines posted in your learning management system.
Late submissions may result in a grade of zero for that module.</p>

<div class="handbook-warning">
  ⚠️ CE hours will NOT be granted on incomplete courses. Ensure you complete all required hours and modules.
</div>

<h4>Tardiness</h4>
<p>Arriving more than 15 minutes late to an in-person session may count as an absence at the instructor's discretion.</p>
"""),
    (3, "Academic Standards", """
<h4>Passing Requirements</h4>
<p>Students must achieve a minimum score of <strong>75%</strong> on all written examinations.
Skills stations require a passing demonstration on each attempt or as specified by the course rubric.</p>

<h4>FISDAP</h4>
<p>EMT and AEMT students are required to maintain a FISDAP account for clinical documentation.
Full tuition must be paid in full before FISDAP access and final testing will be granted.</p>

<h4>National Registry Exams</h4>
<p>PEMSE prepares students to sit for the National Registry of Emergency Medical Technicians (NREMT)
cognitive and psychomotor exams. Passing the NREMT is required to obtain Nebraska licensure.</p>

<h4>Remediation</h4>
<ul>
  <li>Students failing an exam below 70% will be required to complete remediation before retesting.</li>
  <li>Students may retake a written exam once. A second failure may result in dismissal from the program.</li>
</ul>
"""),
    (4, "Clinical Requirements", """
<h4>Required Documentation</h4>
<p>Before beginning any clinical rotation, students must have the following on file with PEMSE:</p>
<ul>
  <li>Copy of driver's license</li>
  <li>Current AHA Healthcare Provider (HCP) CPR certification card</li>
  <li>Up-to-date immunization records (Hepatitis B, Tdap, influenza recommended)</li>
  <li>RN, LPN, or EMT license (if applicable to your course)</li>
</ul>

<h4>Clinical Site Expectations</h4>
<p>Students represent Panhandle EMS Education at all clinical sites. Professional behavior,
appropriate uniform, and respect for patients and staff are mandatory at all times.</p>

<div class="handbook-warning">
  ⚠️ Students asked to leave a clinical site due to conduct issues may be dismissed from the program without a refund.
</div>

<h4>Documentation</h4>
<p>All clinical hours and patient contacts must be documented in FISDAP.
Hours not documented may not count toward program requirements.</p>
"""),
    (5, "Tuition & Refund Policy", """
<h4>2025 Tuition Rates</h4>
<ul>
  <li>Option 1 — EMR Hybrid w/ Textbook: <strong>$750</strong> (min. down $750)</li>
  <li>Option 2 — EMR Hybrid, no textbook: <strong>$650</strong> (min. down $650)</li>
  <li>Option 3 — EMT Hybrid w/ Textbook: <strong>$1,300</strong> (min. down $700)</li>
  <li>Option 4 — EMT Hybrid, no textbook: <strong>$1,100</strong> (min. down $600)</li>
  <li>Option 5 — EMT to AEMT Hybrid Bridge: <strong>$1,200</strong> (min. down $700)</li>
  <li>Option 6 — RN/LPN to EMT Hybrid Bridge: <strong>$1,100</strong> (min. down $600)</li>
  <li>Option 7 — EMT IV Therapy: <strong>$200</strong> (min. down $200)</li>
</ul>

<h4>Payment Schedule</h4>
<p>Minimum down payments must be paid before the first night of class. Students choosing a payment schedule
must work directly with PEMSE. Payments are due at 30, 60, 90, and 120-day intervals from the signed registration date.
The final balance is due before FISDAP and final testing.</p>

<div class="handbook-warning">
  ⚠️ <strong>There are no refunds on PEMSE courses.</strong> CE hours will NOT be granted on incomplete courses.
  PEMSE reserves the right to legally pursue any unpaid tuition.
</div>
"""),
    (6, "Conduct & Professionalism", """
<h4>Professional Standards</h4>
<p>PEMSE expects all students to conduct themselves with the highest degree of professionalism —
in class, during clinical rotations, and when representing PEMSE in the community.</p>

<h4>Prohibited Conduct</h4>
<ul>
  <li>Dishonesty, cheating, or falsification of clinical records</li>
  <li>Harassment or disrespectful behavior toward instructors, peers, or clinical staff</li>
  <li>Reporting to class or a clinical site under the influence of substances</li>
  <li>Unauthorized sharing of patient information (HIPAA)</li>
</ul>

<h4>Social Media</h4>
<p>Students may not post photos, videos, or identifying information regarding patients,
clinical sites, or PEMSE classrooms without explicit written consent.</p>

<h4>Dismissal</h4>
<p>Students found in violation of conduct standards may be dismissed from the program.
Dismissed students are not entitled to a refund per PEMSE policy.</p>
"""),
    (7, "Handbook Acknowledgment", """
<p>By signing this acknowledgment, I confirm that I have received, read, and understood the
<strong>Panhandle EMS Education Student Handbook (2025 edition)</strong>.</p>

<p>I agree to abide by all policies, procedures, and standards outlined in this handbook,
including attendance requirements, academic standards, conduct expectations, and the refund policy.</p>

<p>I understand that failure to comply with these policies may result in dismissal from the program
without a refund, and that PEMSE reserves the right to pursue any unpaid tuition legally.</p>
"""),
]


class Command(BaseCommand):
    help = 'Seed handbook chapters'

    def handle(self, *args, **kwargs):
        for number, title, body in CHAPTERS:
            obj, created = HandbookChapter.objects.update_or_create(
                number=number,
                defaults={'title': title, 'body': body.strip(), 'is_active': True}
            )
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f'{verb}: Chapter {number} — {title}')
        self.stdout.write(self.style.SUCCESS(f'\n✓ {len(CHAPTERS)} chapters seeded.'))
