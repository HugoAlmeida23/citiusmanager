import React, { useState, useEffect, useRef } from "react";
import { Calendar, Database, RefreshCw, Save, X, Info, User, Lock, MailOpen, Briefcase } from "lucide-react";
import api from "../api"; // Usando a mesma estrutura de API que as outras páginas
import Header from "../components/Header"; // Importando o cabeçalho

const TogglNotionIntegration = () => {
  // Estados para controlar a UI e os dados
  const [loading, setLoading] = useState(false);
  const [importSuccess, setImportSuccess] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [databaseId, setDatabaseId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [projectData, setProjectData] = useState([]);
  const [importDetails, setImportDetails] = useState("");
  const [showTooltip, setShowTooltip] = useState(false);
  
  // Estados para credenciais
  const [hasCredentials, setHasCredentials] = useState(false);
  const [showCredentialsForm, setShowCredentialsForm] = useState(false);
  const [credentials, setCredentials] = useState({
    email: "",
    password: "",
    token: "",
    workspace: ""
  });
  const [savingCredentials, setSavingCredentials] = useState(false);
  
  // Refs para os calendários personalizados
  const startDateRef = useRef(null);
  const endDateRef = useRef(null);

  // Verificar credenciais e buscar últimas atualizações quando o componente é montado
  useEffect(() => {
    checkCredentials();
    fetchLastUpdate();
  }, []);

  // Verificar se as credenciais já estão salvas
  const checkCredentials = async () => {
    try {
      const response = await api.get("/api/toggl-notion/check-credentials/");
      setHasCredentials(response.data.exists);
      
      if (!response.data.exists) {
        setShowCredentialsForm(true);
      }
    } catch (error) {
      console.error("Erro ao verificar credenciais:", error);
      setShowCredentialsForm(true);
    }
  };

  // Buscar a data do último update
  const fetchLastUpdate = async () => {
    try {
      const response = await api.get("/api/toggl-notion/last-update/");
      if (response.data && response.data.start_date && response.data.end_date) {
        setLastUpdate({
          startDate: response.data.start_date,
          endDate: response.data.end_date
        });
      }
    } catch (error) {
      console.error("Erro ao buscar último update:", error);
    }
  };

  // Lidar com alterações nas credenciais
  const handleCredentialChange = (e) => {
    const { name, value } = e.target;
    setCredentials(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Salvar credenciais
  const saveCredentials = async (e) => {
    e.preventDefault();
    
    // Validar credenciais
    if (!credentials.email || !credentials.password || !credentials.token || !credentials.workspace) {
      setError("Por favor, preencha todos os campos de credenciais.");
      return;
    }
    
    setSavingCredentials(true);
    setError(null);
    
    try {
      const response = await api.post("/api/toggl-notion/save-credentials/", credentials);
      
      if (response.data && response.data.success) {
        setHasCredentials(true);
        setShowCredentialsForm(false);
      } else {
        throw new Error(response.data.message || "Falha ao salvar credenciais");
      }
    } catch (error) {
      setError(error.response?.data?.message || error.message || "Ocorreu um erro ao salvar as credenciais.");
      console.error("Erro ao salvar credenciais:", error);
    } finally {
      setSavingCredentials(false);
    }
  };

  // Manipular o envio do formulário de importação
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!databaseId || !startDate || !endDate) {
      setError("Por favor, preencha todos os campos obrigatórios.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setImportSuccess(false);
    
    try {
      // Capturar o ID da base de dados do Notion a partir da URL completa
      const notionDbId = extractNotionDatabaseId(databaseId);
      
      if (!notionDbId) {
        throw new Error("ID da base de dados do Notion inválido. Verifique a URL fornecida.");
      }
      
      // Formatar as datas para o formato esperado pela API
      const formattedStartDate = formatDateForAPI(startDate);
      const formattedEndDate = formatDateForAPI(endDate);
      
      // Chamar a API para importar os dados
      const response = await api.post("/api/toggl-notion/import/", {
        notion_database_id: notionDbId,
        start_date: formattedStartDate,
        end_date: formattedEndDate
      });
      
      // Processar a resposta
      if (response.data && response.data.success) {
        setImportSuccess(true);
        
        // Se houver dados de projetos na resposta, atualizar o estado
        if (response.data.projects && response.data.projects.length > 0) {
          setProjectData(response.data.projects);
          
          // Gerar texto de detalhes para exibição
          const details = response.data.projects.map(project => 
            `Projeto: ${project.project_name}\nCliente: ${project.client_name}\nResponsável: ${project.user_id}\nTempo Trabalho: ${formatSeconds(project.seconds)}`
          ).join("\n\n");
          
          setImportDetails(details);
        }
        
        // Atualizar a informação do último update
        fetchLastUpdate();
      }
    } catch (error) {
      setError(error.response?.data?.message || error.message || "Ocorreu um erro durante a importação.");
      console.error("Erro na importação:", error);
    } finally {
      setLoading(false);
    }
  };
  
  // Extrair o ID da base de dados do Notion da URL
  const extractNotionDatabaseId = (url) => {
    // Regex para extrair o ID da URL do Notion
    const idRegex = /\/([^\/\?]+)\?/;
    const match = url.match(idRegex);
    return match ? match[1] : null;
  };
  
  // Formatar data no formato esperado pela API (YYYY-MM-DD)
  const formatDateForAPI = (dateString) => {
    // Se a data já estiver no formato correto, apenas retorna
    if (/^\d{4}-\d{2}-\d{2}/.test(dateString)) {
      return dateString.split(" ")[0]; // Extrair apenas a parte da data
    }
    
    // Caso contrário, converter para o formato correto
    const date = new Date(dateString);
    return date.toISOString().split('T')[0];
  };
  
  // Formatar segundos em uma string legível (HH:MM:SS)
  const formatSeconds = (totalSeconds) => {
    if (!totalSeconds && totalSeconds !== 0) return "00:00:00";
    
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

  // Mostrar formulário de credenciais caso necessário
  const renderCredentialsForm = () => {
    return (
      <div className="bg-white rounded-lg shadow-lg overflow-hidden mb-6">
        <div className="bg-gradient-to-r from-purple-600 to-purple-800 p-6">
          <h2 className="text-xl font-bold text-white">Configurar Dados</h2>
          <p className="text-purple-100 mt-1">
            Configure os seus dados do Toggl e Notion para usar a integração
          </p>
        </div>
        
        <div className="p-6">
          <form onSubmit={saveCredentials} className="space-y-4">
            {/* Email Toggl */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                E-mail do Toggl
              </label>
              <div className="relative mt-1 rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MailOpen className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  id="email"
                  name="email"
                  className="focus:ring-purple-500 focus:border-purple-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                  placeholder="seu.email@exemplo.com"
                  value={credentials.email}
                  onChange={handleCredentialChange}
                  required
                />
              </div>
            </div>

            {/* Senha Toggl */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Palavra-passe do Toggl
              </label>
              <div className="relative mt-1 rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="password"
                  id="password"
                  name="password"
                  className="focus:ring-purple-500 focus:border-purple-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                  placeholder="********"
                  value={credentials.password}
                  onChange={handleCredentialChange}
                  required
                />
              </div>
            </div>
            
            {/* Token Notion */}
            <div>
              <label htmlFor="token" className="block text-sm font-medium text-gray-700 mb-1">
                Token do Notion
              </label>
              <div className="relative mt-1 rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="password"
                  id="token"
                  name="token"
                  className="focus:ring-purple-500 focus:border-purple-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                  placeholder="secret_xxxxxxxxxxxxxxxxxxxxxxxx"
                  value={credentials.token}
                  onChange={handleCredentialChange}
                  required
                />
              </div>
              <p className="mt-1 text-sm text-gray-500">
                Podes criar um token em https://www.notion.so/my-integrations
              </p>
            </div>
            
            {/* ID do Workspace */}
            <div>
              <label htmlFor="workspace" className="block text-sm font-medium text-gray-700 mb-1">
                ID do Workspace do Toggl
              </label>
              <div className="relative mt-1 rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Briefcase className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  id="workspace"
                  name="workspace"
                  className="focus:ring-purple-500 focus:border-purple-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                  placeholder="1234567"
                  value={credentials.workspace}
                  onChange={handleCredentialChange}
                  required
                />
              </div>
              <p className="mt-1 text-sm text-gray-500">
               Podes encontrar o ID do workspace na URL do Toggl Track
              </p>
            </div>
            
            {/* Botão de salvar */}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={savingCredentials}
                className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                {savingCredentials ? (
                  <>
                    <RefreshCw className="animate-spin -ml-1 mr-2 h-5 w-5" />
                    Salvando...
                  </>
                ) : (
                  <>
                    <Save className="-ml-1 mr-2 h-5 w-5" />
                    Salvar Dados
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  };

  return (
    <div className="main">
      <Header />
      <div
        className="p-6 bg-gray-100 min-h-screen"
        style={{ marginLeft: "3%" }}
      >
        {/* Formulário de credenciais (se necessário) */}
        {showCredentialsForm && renderCredentialsForm()}
        
        {/* Container principal de integração */}
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          {/* Cabeçalho */}
          <div className="bg-gradient-to-r from-blue-600 to-blue-800 p-6">
            <h1 className="text-2xl font-bold text-white">Integração Toggl - Notion</h1>
            <p className="text-blue-100 mt-1">
              Importe dados de tempo do Toggl Track para o seu banco de dados do Notion
            </p>
          </div>

          {/* Corpo */}
          <div className="p-6">
            {/* Mostrar último update */}
            {lastUpdate && (
              <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <Info className="h-5 w-5 text-blue-400" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-blue-700">
                      Última atualização: <span className="font-medium">{lastUpdate.startDate}</span> até <span className="font-medium">{lastUpdate.endDate}</span>
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Formulário de importação (apenas exibido se já tiver credenciais) */}
            {hasCredentials && (
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Base de dados Notion */}
                <div>
                  <label htmlFor="notion_database" className="block text-sm font-medium text-gray-700 mb-1">
                    URL da Base de Dados do Notion
                  </label>
                  <div className="relative mt-1 rounded-md shadow-sm">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Database className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                      type="text"
                      id="notion_database"
                      className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                      placeholder="https://www.notion.so/workspace/..."
                      value={databaseId}
                      onChange={(e) => setDatabaseId(e.target.value)}
                      required
                    />
                  </div>
                </div>

                {/* Data inicial e final */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="start_date" className="block text-sm font-medium text-gray-700 mb-1">
                      Data Inicial
                    </label>
                    <div className="relative mt-1 rounded-md shadow-sm">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Calendar className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="date"
                        id="start_date"
                        ref={startDateRef}
                        className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="end_date" className="block text-sm font-medium text-gray-700 mb-1">
                      Data Final
                    </label>
                    <div className="relative mt-1 rounded-md shadow-sm">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Calendar className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="date"
                        id="end_date"
                        ref={endDateRef}
                        className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 pr-12 sm:text-sm border-gray-300 rounded-md py-3"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                </div>

                {/* Botão de importação */}
                <div className="flex justify-end mt-6">
                  <button
                    type="submit"
                    disabled={loading}
                    className="inline-flex items-center px-6 py-3 border border-transparent rounded-md shadow-sm text-base font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? (
                      <>
                        <RefreshCw className="animate-spin -ml-1 mr-2 h-5 w-5" />
                        Importando...
                      </>
                    ) : (
                      <>
                        <Save className="-ml-1 mr-2 h-5 w-5" />
                        Importar Dados
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}

            {/* Mensagens de erro */}
            {error && (
              <div className="mt-6 bg-red-50 border-l-4 border-red-500 p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <X className="h-5 w-5 text-red-400" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Resultado da importação */}
            {importSuccess && (
              <div className="mt-6">
                <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <svg className="h-5 w-5 text-green-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-green-700">
                        Dados importados com sucesso! Foram atualizados {projectData.length} projetos.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Exibir detalhes dos projetos importados */}
                {projectData.length > 0 && (
                  <div className="mt-4 bg-white rounded-lg border border-gray-200 shadow-sm">
                    <div className="px-4 py-5 sm:px-6 mb-4">
                      <h3 className="text-lg leading-6 font-medium text-gray-900">
                        Detalhes dos Projetos Atualizados
                      </h3>
                    </div>
                    <div className="border-t border-gray-200 mb-6">
                      <dl>
                        {projectData.map((project, index) => (
                          <div key={index} className={`px-4 py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 ${index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}`}>
                            <dt className="text-sm font-medium text-gray-500">
                              Projeto
                            </dt>
                            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                              <div>
                                <strong>Nome:</strong> {project.project_name}
                              </div>
                              <div>
                                <strong>Cliente:</strong> {project.client_name}
                              </div>
                              <div>
                                <strong>Responsável:</strong> {project.user_id}
                              </div>
                              <div>
                                <strong>Tempo de Trabalho:</strong> {formatSeconds(project.seconds)}
                              </div>
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TogglNotionIntegration;