# Generated by Django 5.1.5 on 2025-02-26 23:34

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Processo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origem', models.CharField(max_length=100)),
                ('data', models.DateTimeField(auto_now_add=True)),
                ('acto', models.CharField(max_length=100)),
                ('doc', models.TextField()),
                ('tribunal', models.CharField(max_length=100)),
                ('unidade', models.CharField(max_length=100)),
                ('processo', models.CharField(max_length=100)),
                ('especie', models.CharField(max_length=100)),
                ('referencia', models.CharField(max_length=100)),
            ],
        ),
    ]
