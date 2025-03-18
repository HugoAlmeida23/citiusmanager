from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Processo, CitiusAccount


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
        fields  = ["id", "origem", "data", "acto","doc", "tribunal" , "unidade", "processo", "especie", "referencia", "advogado"]
        read_only_fields = ["user"]  # Prevent clients from directly setting the user

         
class CitiusAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitiusAccount
        fields = ['id', 'username', 'password', 'advogado', 'is_active', 'last_used', 'created_at', 'updated_at','email']
        read_only_fields = ['created_at', 'updated_at', 'last_used']
        read_only_fields = ["user"]  # Prevent clients from directly setting the user
