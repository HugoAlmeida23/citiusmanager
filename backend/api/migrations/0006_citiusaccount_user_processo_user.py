# Generated by Django 4.2.20 on 2025-03-16 23:24

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0005_citiusaccount_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='citiusaccount',
            name='user',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.CASCADE, related_name='citius_accounts', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='processo',
            name='user',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.CASCADE, related_name='processos', to=settings.AUTH_USER_MODEL),
        ),
    ]
