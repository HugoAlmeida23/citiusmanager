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
    # Novo campo para status do documento
    DOCUMENT_STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('success', 'Sucesso'),
        ('error', 'Erro'),
    )
    document_status = models.CharField(
        max_length=20, 
        choices=DOCUMENT_STATUS_CHOICES, 
        default='pending'
    )
    document_error_message = models.TextField(blank=True, null=True)  # Mensagem de erro, se houver
    alerted = models.BooleanField(default=False)  # Flag to indicate if the user has been alerted
    # New fields for document management
    document_stored = models.BooleanField(default=False, null=True)  # Flag to indicate if document was successfully stored
    document_type = models.CharField(max_length=50, blank=True, null=True)  # PDF, HTML, etc.
    document_size = models.IntegerField(blank=True, null=True)  # Size in bytes
    last_accessed = models.DateTimeField(blank=True, null=True)  # Track when document was last accessed
    
    # Novo campo para timestamp de criação
    created_at = models.DateTimeField(auto_now_add=True)
    
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
    
class CitiusAccountEmail(models.Model):
    account = models.ForeignKey(CitiusAccount, on_delete=models.CASCADE, related_name='additional_emails')
    email = models.EmailField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['account', 'email']  # Evitar duplicatas
        
    def __str__(self):
        return f"{self.email} ({self.account.username})"
    
# Modelo para o status da aplicação
class SystemStatus(models.Model):
    STATUS_CHOICES = (
        ('active', 'Ativo'),
        ('inactive', 'Inativo'),
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_check = models.DateTimeField(auto_now=True)
    message = models.TextField(blank=True, null=True)  # Para armazenar mensagens sobre o estado
    
    # Metadados sobre checks específicos
    accounts_status = models.JSONField(default=dict, blank=True, null=True)  # Status das contas Citius
    document_errors = models.IntegerField(default=0)  # Contador de erros de documento
    
    class Meta:
        verbose_name = "Status do Sistema"
        verbose_name_plural = "Status do Sistema"
    
    def __str__(self):
        return f"Sistema {self.get_status_display()} - {self.last_check}"


    
    