from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import HandbookChapter, HandbookAcknowledgment


@login_required
def handbook_view(request):
    chapters = HandbookChapter.objects.filter(is_active=True)
    ack = HandbookAcknowledgment.objects.filter(student=request.user).first()
    active_chapter_num = int(request.GET.get('chapter', 1))
    active_chapter = get_object_or_404(HandbookChapter, number=active_chapter_num, is_active=True)

    if request.method == 'POST' and not ack:
        sig_name = request.POST.get('sig_name', '').strip()
        if not sig_name or len(sig_name) < 500:
            messages.error(request, 'Please draw your signature before signing.')
        else:
            ip = request.META.get('REMOTE_ADDR')
            HandbookAcknowledgment.objects.create(
                student=request.user, sig_name=sig_name, ip_address=ip
            )
            request.user.handbook_signed = True
            request.user.handbook_sig_name = sig_name
            request.user.handbook_signed_at = timezone.now()
            request.user.save(update_fields=['handbook_signed', 'handbook_sig_name', 'handbook_signed_at'])
            messages.success(request, 'Handbook signed successfully. Your signature has been recorded.')
            return redirect('handbook')

    return render(request, 'handbook/handbook.html', {
        'chapters': chapters,
        'active_chapter': active_chapter,
        'ack': ack,
        'total_chapters': chapters.count(),
    })
