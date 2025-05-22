import React, { useState, useEffect } from "react";
import { AlertCircle, CheckCircle, RefreshCw, Clock } from "lucide-react";
import api from "../api";

const StatusIndicator = () => {
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/system-status/");
      setStatusData(response.data);
      setError(null);
    } catch (err) {
      console.error("Error fetching system status:", err);
      setError("Falha ao carregar o status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    
    // Atualiza a cada 5 minutos
    const intervalId = setInterval(fetchStatus, 5 * 60 * 1000);
    
    return () => clearInterval(intervalId);
  }, []);

  // Formatar data para exibição
  const formatDateTime = (isoString) => {
    if (!isoString) return "N/A";
    const date = new Date(isoString);
    return date.toLocaleString("pt-PT");
  };

  if (loading && !statusData) {
    return (
      <div className="flex items-center px-4 py-3 rounded-lg bg-blue-600 text-white shadow-md">
        <RefreshCw size={20} className="animate-spin mr-3" />
        <span className="text-base font-medium">Verificando status...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-between px-4 py-3 rounded-lg bg-red-600 text-white shadow-md">
        <div className="flex items-center">
          <AlertCircle size={20} className="mr-3" />
          <span className="text-base font-medium">{error}</span>
        </div>
        <button 
          onClick={fetchStatus}
          className="ml-4 p-1.5 bg-red-700 rounded-full hover:bg-red-800 transition-colors"
          aria-label="Tentar novamente"
          title="Tentar novamente"
        >
          <RefreshCw size={16} />
        </button>
      </div>
    );
  }

  if (!statusData) return null;

  const isActive = statusData.status === "active";
  const bgColor = isActive ? "bg-green-600" : "bg-red-600";
  const statusText = isActive ? "Ativo" : "Inativo";
  const statusColor = isActive ? "text-green-300" : "text-red-300";

  return (
    <div 
      className={`flex flex-col ${bgColor} text-white p-4 rounded-lg shadow-md hover:shadow-lg transition-all cursor-pointer`}
      onClick={() => fetchStatus()}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center">
          {isActive ? (
            <CheckCircle size={22} className="mr-3" />
          ) : (
            <AlertCircle size={22} className="mr-3" />
          )}
          <span className={`text-lg font-bold ${statusColor}`}>{statusText}</span>
        </div>
        
        <button 
          onClick={(e) => {
            e.stopPropagation();
            fetchStatus();
          }}
          className={`p-1.5 ${isActive ? 'bg-green-700' : 'bg-red-700'} rounded-full hover:bg-opacity-80 transition-colors`}
          aria-label="Atualizar status"
          title="Atualizar status"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
        </button>
      </div>
      
      <div className="flex items-center mt-1 text-white opacity-90">
        <Clock size={16} className="mr-2" />
        <span className="text-sm">Última verificação: {formatDateTime(statusData.last_check)}</span>
      </div>
      
      {statusData.message && !isActive && (
        <div className="mt-2 text-sm bg-red-700 p-2 rounded">
          {statusData.message}
        </div>
      )}
    </div>
  );
};

export default StatusIndicator;