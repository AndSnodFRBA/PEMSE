import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import DocumentType, StudentDocument
from .forms import DocumentUploadForm


@login_required
def document_list_view(request):
    doc_types = DocumentType.objects.all()
    uploads = {d.doc_type_id: d for d in StudentDocument.objects.filter(student=request.user).select_related('doc_type')}
    items = [{'type': dt, 'upload': uploads.get(dt.id)} for dt in doc_types]
    return render(request, 'documents/document_list.html', {'items': items})


@login_required
def upload_document_view(request, doc_type_slug):
    doc_type = get_object_or_404(DocumentType, slug=doc_type_slug)
    existing = StudentDocument.objects.filter(student=request.user, doc_type=doc_type).first()
    form = DocumentUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        file = request.FILES['file']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in DocumentType.ALLOWED_EXTENSIONS:
            messages.error(request, 'Only PDF, JPG, and PNG files are accepted.')
            return redirect('upload_document', doc_type_slug=doc_type_slug)

        if existing:
            # Replace existing file
            existing.file.delete(save=False)
            existing.file = file
            existing.status = StudentDocument.Status.PENDING
            existing.save(update_fields=['file', 'status', 'uploaded_at'])
            existing.uploaded_at = None  # triggers auto_now_add reset via signal if needed
            existing.save()
        else:
            StudentDocument.objects.create(
                student=request.user, doc_type=doc_type, file=file
            )

        messages.success(request, f'{doc_type.label} uploaded successfully.')
        return redirect('documents')

    return render(request, 'documents/upload.html', {
        'doc_type': doc_type,
        'existing': existing,
        'form': form,
    })


@login_required
def delete_document_view(request, doc_id):
    doc = get_object_or_404(StudentDocument, pk=doc_id)
    if doc.student != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, 'Document removed.')
    return redirect('documents')
