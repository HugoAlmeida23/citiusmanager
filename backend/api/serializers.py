from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Processo, CitiusAccount, CitiusAccountEmail


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "password"]
        extra_kwargs = {"password": {"write_only": True}}
        
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user     
    
class ProcessoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Processo
        fields  = ["id", "origem", "data", "acto","doc", "tribunal", "unidade", 
                   "processo", "especie", "referencia", "advogado", "created_at"]
        read_only_fields = ["user", "created_at"]  # Prevent clients from directly setting these fields

# Serializer para os emails adicionais
class CitiusAccountEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitiusAccountEmail
        fields = ['id', 'email', 'is_active', 'created_at']
        read_only_fields = ['created_at']
         
class CitiusAccountSerializer(serializers.ModelSerializer):
    # Incluir os emails adicionais na serialização da conta
    additional_emails = CitiusAccountEmailSerializer(many=True, read_only=True)
    
    class Meta:
        model = CitiusAccount
        fields = ['id', 'username', 'password', 'advogado', 'is_active', 
                 'last_used', 'created_at', 'updated_at', 'email', 'additional_emails']
        read_only_fields = ['created_at', 'updated_at', 'last_used', 'user']