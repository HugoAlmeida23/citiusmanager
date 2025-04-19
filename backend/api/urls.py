from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views



# Create a router for ViewSets
router = DefaultRouter()
router.register(r'citius-accounts', views.CitiusAccountViewSet)
router.register(r'account-emails', views.CitiusAccountEmailViewSet)


urlpatterns = [
    path("processos/", views.ProcessoListCreate.as_view(), name="processo-list"),
    path("processos/delete/<int:pk>/", views.ProcessoDelete.as_view(), name="delete-processo"),
    path('refresh-notifications/', views.refresh_notifications, name='refresh_notifications'),
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
    path('test-account/', views.test_account, name='test-account'),
    path('upload/', views.upload_audio, name='upload_audio'),
    path('download/', views.download_transcription, name='download_transcription'),
    path('', include(router.urls)),  # Include router URLs directly without 'api/' prefix
    path('citius-accounts/<int:account_id>/emails/', views.account_emails, name='account-emails'),
    path('toggl-notion/last-update/', views.last_update, name='toggl_notion_last_update'),
    path('toggl-notion/import/', views.import_toggl_data, name='toggl_notion_import'),
    path('toggl-notion/check-credentials/', views.check_credentials, name='toggl_notion_check_credentials'),
    path('toggl-notion/save-credentials/', views.save_credentials, name='toggl_notion_save_credentials'),
]