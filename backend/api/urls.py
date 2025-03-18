from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'citius-accounts', views.CitiusAccountViewSet)

urlpatterns = [
    path("processos/", views.ProcessoListCreate.as_view(), name="processo-list"),
    path("processos/delete/<int:pk>/", views.ProcessoDelete.as_view(), name="delete-processo"),
    path('refresh-notifications/', views.refresh_notifications, name='refresh_notifications'),
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
    path('test-account/', views.test_account, name='test-account'),
    path('upload/', views.upload_audio, name='upload_audio'),
    path('download/', views.download_transcription, name='download_transcription'),
    path('', include(router.urls)),  # Include router URLs directly without 'api/' prefix
]