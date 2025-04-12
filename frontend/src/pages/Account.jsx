import React, { useState, useEffect, useRef } from "react";
import {
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  Eye,
  EyeOff,
  RefreshCw,
  Mail,
} from "lucide-react";
import api from "../api";
import Header from "../components/Header";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const AccountsManagement = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [testingAccount, setTestingAccount] = useState(false);
  const [testResult, setTestResult] = useState(null);
  
  // Estados para gerenciar emails adicionais
  const [showEmailForm, setShowEmailForm] = useState(null); // ID da conta para mostrar formulário de email
  const [newEmail, setNewEmail] = useState("");
  const [accountEmails, setAccountEmails] = useState({}); // {accountId: [emails]}
  const [loadingEmails, setLoadingEmails] = useState(false);
  
  // Estado para gerenciar múltiplos emails na criação da conta
  const [multipleEmails, setMultipleEmails] = useState(false); // Se true, mostra campos para múltiplos emails
  const [additionalEmails, setAdditionalEmails] = useState([]); // Lista de emails adicionais durante a criação da conta
  const [newAdditionalEmail, setNewAdditionalEmail] = useState(""); // Campo para novo email adicional
  const emailInputRef = useRef(null);

  // Form state
  const [newAccount, setNewAccount] = useState({
    username: "",
    password: "",
    advogado: "",
    email: "",
    is_active: true,
  });

  // Password visibility state
  const [showPasswords, setShowPasswords] = useState({});

  // Fetch accounts on component mount
  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/citius-accounts/");
      setAccounts(response.data);
      // Initialize password visibility state
      const passwordVisibility = {};
      response.data.forEach((account) => {
        passwordVisibility[account.id] = false;
      });
      setShowPasswords(passwordVisibility);
      toast.success("Contas carregadas!");
      
      // Carregar emails adicionais para cada conta
      response.data.forEach(account => {
        fetchAccountEmails(account.id);
      });
    } catch (err) {
      setError("Erro a carregar contas: " + (err.response?.data?.message || err.message));
      toast.error("Erro a carregar contas: " + (err.response?.data?.message || err.message));
      console.error("Erro a carregar contas:", err);
    } finally {
      setLoading(false);
    }
  };
  
  // Função para adicionar email à lista de emails adicionais durante a criação da conta
  const addToAdditionalEmails = () => {
    if (!newAdditionalEmail || !newAdditionalEmail.includes('@')) {
      toast.error("Por favor, insira um endereço de email válido");
      return;
    }
    
    // Verificar se este email já está na lista
    if (additionalEmails.includes(newAdditionalEmail)) {
      toast.error("Este email já foi adicionado");
      return;
    }
    
    setAdditionalEmails([...additionalEmails, newAdditionalEmail]);
    setNewAdditionalEmail("");
  };
  
  // Função para remover um email da lista de emails adicionais
  const removeFromAdditionalEmails = (emailToRemove) => {
    setAdditionalEmails(additionalEmails.filter(email => email !== emailToRemove));
  };
  
  // Função para buscar emails adicionais de uma conta
  const fetchAccountEmails = async (accountId) => {
    try {
      const response = await api.get(`/api/citius-accounts/${accountId}/emails/`);
      setAccountEmails(prev => ({
        ...prev,
        [accountId]: response.data
      }));
    } catch (err) {
      console.error(`Erro ao carregar emails da conta ${accountId}:`, err);
      // Não mostrar toast para não sobrecarregar o usuário com notificações
    }
  };
  
  // Função para adicionar um novo email a uma conta existente
  const addEmailToAccount = async (accountId, emailToAdd) => {
    if (!emailToAdd || !emailToAdd.includes('@')) {
      toast.error("Por favor, insira um endereço de email válido");
      return;
    }
    
    setLoadingEmails(true);
    try {
      const response = await api.post(`/api/citius-accounts/${accountId}/emails/`, {
        email: emailToAdd,
        is_active: true
      });
      
      // Atualizar o estado local
      setAccountEmails(prev => ({
        ...prev,
        [accountId]: [...(prev[accountId] || []), response.data]
      }));
      
      // Limpar o formulário
      setShowEmailForm(null);
      
      toast.success("Email adicionado com sucesso!");
    } catch (err) {
      toast.error("Erro ao adicionar email: " + (err.response?.data?.error || err.message));
    } finally {
      setLoadingEmails(false);
    }
  };
  
  // Função para remover um email de uma conta
  const removeEmailFromAccount = async (accountId, emailId) => {
    if (!window.confirm("Tem certeza que deseja remover este email?")) {
      return;
    }
    
    setLoadingEmails(true);
    try {
      await api.delete(`/api/citius-accounts/${accountId}/emails/`, {
        data: { email_id: emailId }
      });
      
      // Atualizar o estado local
      setAccountEmails(prev => ({
        ...prev,
        [accountId]: (prev[accountId] || []).filter(email => email.id !== emailId)
      }));
      
      toast.success("Email removido com sucesso!");
    } catch (err) {
      toast.error("Erro ao remover email: " + (err.response?.data?.error || err.message));
    } finally {
      setLoadingEmails(false);
    }
  };

  const handleInputChange = (e, isEditMode = false, accountId = null) => {
    const { name, value, type, checked } = e.target;
    const inputValue = type === "checkbox" ? checked : value;

    if (isEditMode) {
      // Update existing account
      setAccounts(
        accounts.map((account) =>
          account.id === accountId
            ? { ...account, [name]: inputValue }
            : account
        )
      );
    } else {
      // Update new account form
      setNewAccount({ ...newAccount, [name]: inputValue });
    }
  };

  // Função para adicionar uma nova conta e seus emails adicionais
  const handleAddAccount = async () => {
    try {
      setLoading(true);
      
      // Primeiro, criar a conta principal
      const response = await api.post("/api/citius-accounts/", newAccount);
      const newAccountData = response.data;
      
      // Se houver emails adicionais, adicioná-los à conta
      if (additionalEmails.length > 0) {
        const emailPromises = additionalEmails.map(email => 
          api.post(`/api/citius-accounts/${newAccountData.id}/emails/`, {
            email: email,
            is_active: true
          })
        );
        
        // Aguardar todas as adições de email
        await Promise.all(emailPromises);
        
        // Atualizar o estado local com os emails adicionais
        setAccountEmails(prev => ({
          ...prev,
          [newAccountData.id]: emailPromises.map((_, index) => ({ 
            id: index, // temporário, será substituído pelo fetchAccountEmails
            email: additionalEmails[index]
          }))
        }));
      }
      
      // Atualizar a lista de contas
      setAccounts([...accounts, newAccountData]);
      
      // Limpar os formulários
      setNewAccount({
        username: "",
        password: "",
        advogado: "",
        email: "",
        is_active: true,
      });
      setAdditionalEmails([]);
      setMultipleEmails(false);
      setShowAddForm(false);
      
      toast.success("Conta adicionada com sucesso!");
      
      // Recarregar emails para ter os IDs corretos
      fetchAccountEmails(newAccountData.id);
      
    } catch (err) {
      setError("Erro a adicionar conta! " + (err.response?.data?.message || err.message));
      toast.error("Erro a adicionar conta! " + (err.response?.data?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateAccount = async (accountId) => {
    try {
      setLoading(true);
      const accountToUpdate = accounts.find((acc) => acc.id === accountId);
      const response = await api.put(`/api/citius-accounts/${accountId}/`, accountToUpdate);
      setAccounts(
        accounts.map((acc) => (acc.id === accountId ? response.data : acc))
      );
      setEditingId(null);
      toast.success("Conta atualizada com sucesso!");
    } catch (err) {
      setError("Erro a atualizar conta: " + (err.response?.data?.message || err.message));
      toast.error("Erro a atualizar conta: " + (err.response?.data?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async (accountId) => {
    if (!window.confirm("Tens a certeza que queres remover esta conta?"))
      return;

    try {
      setLoading(true);
      await api.delete(`/api/citius-accounts/${accountId}/`);
      setAccounts(accounts.filter((acc) => acc.id !== accountId));
      toast.success("Conta eliminada com sucesso!");
    } catch (err) {
      setError("Erro a eliminar conta: " + (err.response?.data?.message || err.message));
      toast.error("Erro a eliminar conta: " + (err.response?.data?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleTestAccount = async (account) => {
    setTestingAccount(true);
    setTestResult(null);

    try {
      const response = await api.post("/api/test-account/", {
        username: account.username,
        password: account.password,
      });

      setTestResult({
        success: true,
        message: "Teste de conexão feita com sucesso! Conta validada!",
      });
      toast.success("Teste de conexão feita com sucesso! Conta validada!");
    } catch (err) {
      setTestResult({
        success: false,
        message:
          "Connection failed: " +
          (err.response?.data?.message || "Invalid credentials"),
      });
      toast.error("Conexão falhou!" + "Credenciais inválidas!");
    } finally {
      setTestingAccount(false);

      // Clear test result after 5 seconds
      setTimeout(() => {
        setTestResult(null);
      }, 5000);
    }
  };

  const togglePasswordVisibility = (accountId) => {
    setShowPasswords({
      ...showPasswords,
      [accountId]: !showPasswords[accountId],
    });
  };

  // Componente para exibir os emails de uma conta
  const AccountEmailsList = ({ accountId }) => {
    const emails = accountEmails[accountId] || [];
    
    return (
      <div className="px-6 py-2 bg-gray-50">
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-sm font-medium text-gray-700">Emails Adicionais</h4>
        </div>
        
        

        {showEmailForm === accountId && (
          <div className="flex mb-2 space-x-2">
            <input 
              type="email"
              ref={emailInputRef}
              defaultValue=""
              placeholder="novo@email.com"
              className="text-sm p-1 border rounded flex-1"
            />
            <button
              onClick={() => {
                const emailValue = emailInputRef.current.value;
                if (emailValue) {
                  addEmailToAccount(accountId, emailValue);
                  emailInputRef.current.value = ""; // Limpar após adicionar
                }
              }}
              disabled={loadingEmails}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              {loadingEmails ? "..." : "Adicionar"}
            </button>
            <button
              onClick={() => {
                setShowEmailForm(null);
              }}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Cancelar
            </button>
          </div>
        )}
        
        {emails.length === 0 ? (
          <p className="text-xs text-gray-500 italic">Nenhum email adicional cadastrado</p>
        ) : (
          <ul className="space-y-1">
            {emails.map(email => (
              <li key={email.id} className="flex justify-between items-center text-sm">
                <span className="text-gray-700">
                  <Mail size={12} className="inline mr-1 text-blue-500" />
                  {email.email}
                </span>
                <button 
                  onClick={() => removeEmailFromAccount(accountId, email.id)}
                  className="text-red-500 hover:text-red-700"
                  title="Remover email"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  if (loading && accounts.length === 0) {
    return (
      <div className="flex justify-center items-center p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="main">
      <Header />
      <div className="content-container" style={{ paddingTop: "1%" }}>
        <div
          className="bg-white p-6 rounded-lg shadow-md"
          style={{ marginLeft: "5%", marginRight: "5%", marginTop: "5%" }}
        >
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">
              Contas da Citius
            </h2>
            <div className="flex space-x-2">
              <button
                onClick={() => {
                  setShowAddForm(!showAddForm);
                  if (showAddForm) {
                    // Resetar o estado se estiver fechando o formulário
                    setAdditionalEmails([]);
                    setMultipleEmails(false);
                  }
                }}
                className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {showAddForm ? (
                  <X size={16} className="mr-2" />
                ) : (
                  <Plus size={16} className="mr-2" />
                )}
                {showAddForm ? "Cancelar" : "Adicionar Nova Conta"}
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4">
              <p>{error}</p>
              <button
                className="text-sm underline mt-1"
                onClick={() => setError(null)}
              >
                Dispensar
              </button>
            </div>
          )}

          {testResult && (
            <div
              className={`${
                testResult.success
                  ? "bg-green-100 border-green-500 text-green-700"
                  : "bg-red-100 border-red-500 text-red-700"
              } border-l-4 p-4 mb-4`}
            >
              <p>{testResult.message}</p>
            </div>
          )}

          {/* Add Account Form */}
          {showAddForm && (
            <div className="bg-gray-50 p-4 rounded-md mb-6 border border-gray-200">
              <h3 className="font-medium text-lg mb-4 text-gray-700">
                Adicionar Nova Conta
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username
                  </label>
                  <input
                    type="text"
                    name="username"
                    value={newAccount.username}
                    onChange={(e) => handleInputChange(e)}
                    className="w-full p-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="email@example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showPasswords["new"] ? "text" : "password"}
                      name="password"
                      value={newAccount.password}
                      onChange={(e) => handleInputChange(e)}
                      className="w-full p-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Password"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPasswords({
                          ...showPasswords,
                          new: !showPasswords["new"],
                        })
                      }
                      className="absolute right-2 top-2 text-gray-400"
                    >
                      {showPasswords["new"] ? (
                        <EyeOff size={18} />
                      ) : (
                        <Eye size={18} />
                      )}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Advogado (Lawyer)
                  </label>
                  <input
                    type="text"
                    name="advogado"
                    value={newAccount.advogado}
                    onChange={(e) => handleInputChange(e)}
                    className="w-full p-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Nome do advogado"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    E-mail Principal
                  </label>
                  <input
                    type="text"
                    name="email"
                    value={newAccount.email}
                    onChange={(e) => handleInputChange(e)}
                    className="w-full p-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="email@example.com"
                  />
                </div>
                
                {/* Adicionar emails adicionais */}
                <div className="md:col-span-2 mt-3">
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      Emails Adicionais
                    </label>
                    <button
                      type="button"
                      onClick={() => setMultipleEmails(!multipleEmails)}
                      className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      {multipleEmails ? "Ocultar" : "Adicionar Mais Emails"}
                    </button>
                  </div>
                  
                  {multipleEmails && (
                    <div className="mb-3 p-3 border border-gray-200 rounded-md bg-white">
                      <div className="flex mb-2 space-x-2">
                        <input 
                          type="email"
                          value={newAdditionalEmail}
                          onChange={(e) => setNewAdditionalEmail(e.target.value)}
                          placeholder="adicional@email.com"
                          className="flex-1 p-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <button
                          onClick={addToAdditionalEmails}
                          className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                        >
                          <Plus size={14} className="inline mr-1" />
                          Adicionar
                        </button>
                      </div>
                      
                      {additionalEmails.length > 0 ? (
                        <div>
                          <p className="text-sm font-medium text-gray-700 mb-1">Emails a adicionar:</p>
                          <ul className="space-y-2">
                            {additionalEmails.map((email, index) => (
                              <li key={index} className="flex justify-between items-center text-sm p-2 bg-gray-50 rounded">
                                <span className="text-gray-700">
                                  <Mail size={14} className="inline mr-1 text-blue-500" />
                                  {email}
                                </span>
                                <button 
                                  onClick={() => removeFromAdditionalEmails(email)}
                                  className="text-red-500 hover:text-red-700"
                                  title="Remover email"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500 italic">Nenhum email adicional informado</p>
                      )}
                    </div>
                  )}
                </div>
                
                <div className="flex items-center mt-2">
                  <input
                    type="checkbox"
                    id="is_active_new"
                    name="is_active"
                    checked={newAccount.is_active}
                    onChange={(e) => handleInputChange(e)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label
                    htmlFor="is_active_new"
                    className="ml-2 block text-sm text-gray-700"
                  >
                    Ativo
                  </label>
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={() => handleTestAccount(newAccount)}
                  className="flex items-center px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 mr-2"
                  disabled={
                    !newAccount.username ||
                    !newAccount.password ||
                    testingAccount
                  }
                >
                  {testingAccount ? (
                    <span className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white mr-2"></span>
                  ) : null}
                  Testar Conexão
                </button>
                <button
                  onClick={handleAddAccount}
                  className="flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                  disabled={
                    !newAccount.username ||
                    !newAccount.password ||
                    !newAccount.advogado
                  }
                >
                  <Save size={16} className="mr-2" />
                  Salvar Conta
                </button>
              </div>
            </div>
          )}

          {/* Accounts Table */}
          {accounts.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full bg-white">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Username
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Password
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Advogado
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      E-mail Principal
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Último Uso
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ações
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {accounts.map((account) => (
                    <React.Fragment key={account.id}>
                      <tr>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {editingId === account.id ? (
                            <input
                              type="text"
                              name="username"
                              value={account.username}
                              onChange={(e) =>
                                handleInputChange(e, true, account.id)
                              }
                              className="w-full p-1 border rounded-md"
                            />
                          ) : (
                            account.username
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {editingId === account.id ? (
                            <div className="relative">
                              <input
                                type={
                                  showPasswords[account.id] ? "text" : "password"
                                }
                                name="password"
                                value={account.password}
                                onChange={(e) =>
                                  handleInputChange(e, true, account.id)
                                }
                                className="w-full p-1 border rounded-md"
                              />
                              <button
                                type="button"
                                onClick={() =>
                                  togglePasswordVisibility(account.id)
                                }
                                className="absolute right-2 top-1 text-gray-400"
                              >
                                {showPasswords[account.id] ? (
                                  <EyeOff size={16} />
                                ) : (
                                  <Eye size={16} />
                                )}
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center">
                              <span>
                                {showPasswords[account.id]
                                  ? account.password
                                  : "••••••••"}
                              </span>
                              <button
                                onClick={() =>
                                  togglePasswordVisibility(account.id)
                                }
                                className="ml-2 text-gray-400 hover:text-gray-600"
                              >
                                {showPasswords[account.id] ? (
                                  <EyeOff size={16} />
                                ) : (
                                  <Eye size={16} />
                                )}
                              </button>
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {editingId === account.id ? (
                            <input
                              type="text"
                              name="advogado"
                              value={account.advogado}
                              onChange={(e) =>
                                handleInputChange(e, true, account.id)
                              }
                              className="w-full p-1 border rounded-md"
                            />
                          ) : (
                            account.advogado
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {editingId === account.id ? (
                            <input
                              type="text"
                              name="email"
                              value={account.email}
                              onChange={(e) =>
                                handleInputChange(e, true, account.id)
                              }
                              className="w-full p-1 border rounded-md"
                            />
                          ) : (
                            <div className="flex items-center">
                              <Mail size={14} className="mr-1 text-blue-500" />
                              {account.email || <span className="text-gray-400 italic">Não definido</span>}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {editingId === account.id ? (
                            <div className="flex items-center">
                            <input
                              type="checkbox"
                              id={`is_active_${account.id}`}
                              name="is_active"
                              checked={account.is_active}
                              onChange={(e) =>
                                handleInputChange(e, true, account.id)
                              }
                              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <label
                              htmlFor={`is_active_${account.id}`}
                              className="ml-2 block text-sm text-gray-700"
                            >
                              Ativo
                            </label>
                          </div>
                        ) : (
                          <span
                            className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                              account.is_active
                                ? "bg-green-100 text-green-800"
                                : "bg-red-100 text-red-800"
                            }`}
                          >
                            {account.is_active ? "Ativo" : "Inativo"}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {account.last_used
                          ? new Date(account.last_used).toLocaleString()
                          : "Nunca"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        {editingId === account.id ? (
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleUpdateAccount(account.id)}
                              className="text-green-600 hover:text-green-900"
                            >
                              <Save size={18} />
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="text-gray-600 hover:text-gray-900"
                            >
                              <X size={18} />
                            </button>
                          </div>
                        ) : (
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleTestAccount(account)}
                              className="text-blue-600 hover:text-blue-900 p-2 rounded-full transition-colors duration-200 hover:bg-blue-100"
                              title="Testar Conta"
                            >
                              <RefreshCw size={16} />
                            </button>
                            <button
                              onClick={() => setEditingId(account.id)}
                              className="text-blue-600 hover:text-blue-900 p-2 rounded-full transition-colors duration-200 hover:bg-blue-100"
                              title="Editar Conta"
                            >
                              <Edit size={16} />
                            </button>
                            <button
                              onClick={() => handleDeleteAccount(account.id)}
                              className="text-blue-600 hover:text-blue-900 p-2 rounded-full transition-colors duration-200 hover:bg-blue-100"
                              title="Apagar Conta"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {/* Linha expandida para emails adicionais */}
                    {editingId === account.id ? (
                    <tr>
                      <td colSpan="7" className="border-t-0 p-0">
                        <div className="bg-gray-50 border-t border-gray-100">
                          <button 
                            onClick={() => {
                              // Se já está aberto o formulário, fecha.
                              // Se não está aberto, abre e busca os emails
                              if (showEmailForm === account.id) {
                                setShowEmailForm(null);
                              } else {
                                setShowEmailForm(account.id);
                                fetchAccountEmails(account.id);
                              }
                            }}
                            className="flex items-center w-full px-6 py-2 text-left text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50"
                          >
                            {showEmailForm === account.id ? (
                              <>
                                <X size={14} className="mr-1" /> Ocultar Emails Adicionais
                              </>
                            ) : (
                              <>
                                <Mail size={14} className="mr-1" /> Gerir Emails Adicionais
                              </>
                            )}
                          </button>
                          
                          {showEmailForm === account.id && (
                            <AccountEmailsList accountId={account.id} />
                          )}
                        </div>
                      </td>
                    </tr>
                    ) : (
                      <tr className="h-4" key={`spacer-${account.id}`}>
                        <td colSpan="7"></td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            Nenhuma conta encontrada! Adicione a sua primeira conta da Citius.
          </div>
        )}
      </div>
    </div>
  </div>
);
};

export default AccountsManagement;