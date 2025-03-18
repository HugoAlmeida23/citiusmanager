from django.db import models
from django.contrib.auth.models import User

class Processo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processos', default="1")
    
    origem = models.CharField(max_length=100)
    data = models.DateField(auto_now_add=True)
    acto = models.CharField(max_length=100)
    doc = models.TextField()  # URL to document in Supabase storage
    tribunal = models.CharField(max_length=100)
    unidade = models.CharField(max_length=100)
    processo = models.CharField(max_length=100)
    especie = models.CharField(max_length=100)
    referencia = models.CharField(max_length=100)
    advogado = models.CharField(max_length=100, default="Geral")
    
    # New fields for document management
    document_stored = models.BooleanField(default=False, null=True)  # Flag to indicate if document was successfully stored
    document_type = models.CharField(max_length=50, blank=True, null=True)  # PDF, HTML, etc.
    document_size = models.IntegerField(blank=True, null=True)  # Size in bytes
    last_accessed = models.DateTimeField(blank=True, null=True)  # Track when document was last accessed
    
    def __str__(self):
        return self.acto

class CitiusAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='citius_accounts', default="1")

    username = models.CharField(max_length=100)  # Login for Citius
    password = models.CharField(max_length=100)  # Password for Citius
    advogado = models.CharField(max_length=100)  # Lawyer name associated with this account
    is_active = models.BooleanField(default=True)  # To enable/disable accounts
    last_used = models.DateTimeField(null=True, blank=True)  # Track when the account was last used
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    email = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return f"{self.username} ({self.advogado})"