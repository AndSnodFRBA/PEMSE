from django.urls import path
from . import views

urlpatterns = [
    path('',                            views.document_list_view,   name='documents'),
    path('<slug:doc_type_slug>/upload/', views.upload_document_view, name='upload_document'),
    path('<int:doc_id>/delete/',         views.delete_document_view, name='delete_document'),
]
