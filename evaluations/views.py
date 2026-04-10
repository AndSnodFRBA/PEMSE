import io
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from staff.mixins import staff_required

from .forms import AddRotationForm, PreceptorEvalForm, StudentSiteEvalForm
from .models import ClinicalRotation, PreceptorEvaluation, StudentSiteEvaluation


# ── Student views ─────────────────────────────────────────────────────────────

@login_required
def rotation_log(request):
    rotations = (
        ClinicalRotation.objects
        .filter(student=request.user)
        .select_related('course')
        .prefetch_related('preceptor_eval', 'student_eval')
    )

    total_hours    = sum(r.hours_completed for r in rotations)
    total_contacts = sum(r.patient_contacts for r in rotations)

    return render(request, 'evaluations/rotation_log.html', {
        'rotations':      rotations,
        'total_hours':    total_hours,
        'total_contacts': total_contacts,
    })


@login_required
def add_rotation(request):
    from courses.models import CourseEnrollment
    enrollment = CourseEnrollment.objects.filter(student=request.user).first()

    initial = {'course': enrollment.course if enrollment else None}
    form    = AddRotationForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        rotation         = form.save(commit=False)
        rotation.student = request.user
        rotation.save()

        eval_request = PreceptorEvaluation.objects.create(
            rotation        = rotation,
            preceptor_name  = form.cleaned_data['preceptor_name'],
            preceptor_email = form.cleaned_data['preceptor_email'],
            preceptor_title = form.cleaned_data.get('preceptor_title', ''),
            token_expires   = timezone.now() + timedelta(days=14),
        )

        preceptor_link = request.build_absolute_uri(
            f'/evaluations/preceptor/{eval_request.token}/'
        )

        return render(request, 'evaluations/add_rotation_success.html', {
            'rotation':       rotation,
            'eval_request':   eval_request,
            'preceptor_link': preceptor_link,
        })

    return render(request, 'evaluations/add_rotation.html', {'form': form})


@login_required
def site_eval(request, pk):
    rotation = get_object_or_404(ClinicalRotation, pk=pk, student=request.user)

    if hasattr(rotation, 'student_eval'):
        messages.info(request, 'You have already submitted a site evaluation for this rotation.')
        return redirect('rotation_log')

    form = StudentSiteEvalForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        eval_obj          = form.save(commit=False)
        eval_obj.rotation = rotation
        eval_obj.save()
        messages.success(request, 'Site evaluation submitted. Thank you!')
        return redirect('rotation_log')

    return render(request, 'evaluations/site_eval.html', {
        'form':     form,
        'rotation': rotation,
    })


# ── Preceptor public views (no login required) ────────────────────────────────

def preceptor_eval(request, token):
    eval_request = get_object_or_404(PreceptorEvaluation, token=token)

    if eval_request.status == PreceptorEvaluation.Status.COMPLETED:
        return render(request, 'evaluations/preceptor_already_submitted.html', {
            'eval': eval_request,
        })

    # Auto-expire if past deadline
    if timezone.now() > eval_request.token_expires:
        if eval_request.status != PreceptorEvaluation.Status.EXPIRED:
            eval_request.status = PreceptorEvaluation.Status.EXPIRED
            eval_request.save(update_fields=['status'])
        return render(request, 'evaluations/preceptor_expired.html', {'eval': eval_request})

    form = PreceptorEvalForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        for field, value in form.cleaned_data.items():
            setattr(eval_request, field, value)

        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        eval_request.preceptor_ip = (
            x_forwarded.split(',')[0].strip() if x_forwarded
            else request.META.get('REMOTE_ADDR')
        )
        eval_request.completed_at = timezone.now()
        eval_request.status       = PreceptorEvaluation.Status.COMPLETED
        eval_request.save()

        return redirect('preceptor_submitted', token=token)

    return render(request, 'evaluations/preceptor_eval.html', {
        'form':     form,
        'eval':     eval_request,
        'rotation': eval_request.rotation,
    })


def preceptor_submitted(request, token):
    eval_request = get_object_or_404(PreceptorEvaluation, token=token)
    return render(request, 'evaluations/preceptor_submitted.html', {'eval': eval_request})


# ── Staff views ───────────────────────────────────────────────────────────────

@staff_required
def staff_eval_list(request):
    evals = (
        PreceptorEvaluation.objects
        .select_related('rotation__student', 'rotation')
        .order_by('-rotation__rotation_date')
    )

    status    = request.GET.get('status', '')
    site      = request.GET.get('site', '')
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    if status:
        evals = evals.filter(status=status)
    if site:
        evals = evals.filter(rotation__site_name__icontains=site)
    if date_from:
        evals = evals.filter(rotation__rotation_date__gte=date_from)
    if date_to:
        evals = evals.filter(rotation__rotation_date__lte=date_to)

    site_evals = (
        StudentSiteEvaluation.objects
        .select_related('rotation__student', 'rotation')
        .order_by('-completed_at')
    )

    pending_count   = PreceptorEvaluation.objects.filter(status=PreceptorEvaluation.Status.PENDING).count()
    completed_count = PreceptorEvaluation.objects.filter(status=PreceptorEvaluation.Status.COMPLETED).count()

    return render(request, 'staff/eval_list.html', {
        'evals':           evals,
        'site_evals':      site_evals,
        'pending_count':   pending_count,
        'completed_count': completed_count,
        'filters': {
            'status':    status,
            'site':      site,
            'date_from': date_from,
            'date_to':   date_to,
        },
    })


@staff_required
def staff_eval_detail(request, pk):
    rotation       = get_object_or_404(ClinicalRotation, pk=pk)
    preceptor_eval_obj = getattr(rotation, 'preceptor_eval', None)
    student_eval_obj   = getattr(rotation, 'student_eval', None)

    return render(request, 'staff/eval_detail.html', {
        'rotation':       rotation,
        'preceptor_eval': preceptor_eval_obj,
        'student_eval':   student_eval_obj,
    })


@staff_required
def staff_eval_pdf(request, pk):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rotation = get_object_or_404(ClinicalRotation, pk=pk)
    pe       = getattr(rotation, 'preceptor_eval', None)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch,  bottomMargin=0.75*inch,
    )

    styles  = getSampleStyleSheet()
    navy    = colors.HexColor('#2B5EA7')
    lt_gray = colors.HexColor('#f3f6fb')

    h1 = ParagraphStyle('h1', parent=styles['Heading1'], textColor=navy, fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], textColor=navy, fontSize=11, spaceBefore=12, spaceAfter=4)
    body = styles['Normal']
    body.fontSize = 9

    def section(title):
        return [Paragraph(title, h2), Spacer(1, 4)]

    def kv_table(data):
        t = Table(data, colWidths=[2.5*inch, 4.25*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (0, -1), lt_gray),
            ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 9),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#d1dae8')),
            ('ROWBACKGROUNDS',(0, 0), (-1, -1), [colors.white, lt_gray]),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ]))
        return t

    SCORE_LABELS = {
        1: 'Unsatisfactory',
        2: 'Below Expectations',
        3: 'Meets Expectations',
        4: 'Exceeds Expectations',
        5: 'Outstanding',
    }

    def score_label(val):
        return f"{val} — {SCORE_LABELS[val]}" if val and val in SCORE_LABELS else '—'

    story = [
        Paragraph('Panhandle EMS Education', h1),
        Paragraph(
            'Clinical Rotation — Preceptor Evaluation',
            ParagraphStyle('sub', parent=body, textColor=colors.HexColor('#5a7a9a'), fontSize=10),
        ),
        Spacer(1, 10),
    ]

    story += section('Rotation Information')
    location = ', '.join(filter(None, [rotation.site_address, rotation.site_city])) or '—'
    story.append(kv_table([
        ['Student',          rotation.student.get_full_name()],
        ['Site Name',        rotation.site_name],
        ['Site Type',        rotation.get_site_type_display()],
        ['Location',         location],
        ['Rotation Date',    str(rotation.rotation_date)],
        ['Hours Completed',  str(rotation.hours_completed)],
        ['Patient Contacts', str(rotation.patient_contacts)],
    ]))

    if pe:
        story += section('Preceptor Information')
        story.append(kv_table([
            ['Preceptor Name', pe.preceptor_name],
            ['Email',          pe.preceptor_email],
            ['Title',          pe.preceptor_title or '—'],
            ['Status',         pe.get_status_display()],
            ['Completed',      pe.completed_at.strftime('%B %d, %Y %I:%M %p') if pe.completed_at else '—'],
        ]))

        if pe.status == PreceptorEvaluation.Status.COMPLETED:
            story += section('Professional Behavior')
            story.append(kv_table([
                ['Professional Appearance',   score_label(pe.appearance_professional)],
                ['Punctuality',               score_label(pe.punctuality)],
                ['Communication — Patients',  score_label(pe.communication_patients)],
                ['Communication — Team',      score_label(pe.communication_team)],
                ['Attitude / Motivation',     score_label(pe.attitude_motivation)],
            ]))

            story += section('Clinical Skills')
            story.append(kv_table([
                ['Patient Assessment',        score_label(pe.patient_assessment)],
                ['Clinical Skills Perf.',     score_label(pe.clinical_skills_performance)],
                ['Critical Thinking',         score_label(pe.critical_thinking)],
                ['Medical Knowledge',         score_label(pe.medical_knowledge)],
                ['Documentation',             score_label(pe.documentation)],
            ]))

            story += section('Overall Assessment')
            story.append(kv_table([
                ['Overall Performance',       score_label(pe.overall_performance)],
                ['Recommended to Pass',       'Yes' if pe.recommended_to_pass else 'No' if pe.recommended_to_pass is not None else '—'],
                ['Average Score',             str(pe.average_score()) if pe.average_score() else '—'],
            ]))

            if any([pe.strengths, pe.areas_for_improvement, pe.additional_comments]):
                story += section('Written Feedback')
                story.append(kv_table([
                    ['Strengths',             pe.strengths or '—'],
                    ['Areas for Improvement', pe.areas_for_improvement or '—'],
                    ['Additional Comments',   pe.additional_comments or '—'],
                ]))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'Generated {timezone.now().strftime("%B %d, %Y %I:%M %p")} — PEMSE Student Portal',
        ParagraphStyle('footer', parent=body, textColor=colors.HexColor('#999999'), fontSize=8),
    ))

    doc.build(story)
    buf.seek(0)

    safe_name = ''.join(
        c if c.isalnum() or c in '-_ ' else ''
        for c in rotation.student.get_full_name()
    ).strip()
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="PEMSE-{safe_name}-preceptor-eval.pdf"'
    )
    return response
