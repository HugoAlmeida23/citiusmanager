import React, { useState, useEffect } from "react";
import {
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  Eye,
  EyeOff,
  RefreshCw,
} from "lucide-react";
import api from "../api";
import Header from "../components/Header";
import { toast } from "react-toastify";  // Import toast
import "react-toastify/dist/ReactToastify.css"; // Import toast styles

const AccountsManagement = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [testingAccount, setTestingAccount] = useState(false);
  const [testResult, setTestResult] = useState(null);

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
    } catch (err) {
      setError("Erro a carregar contas: " + (err.response?.data?.message || err.message));
      toast.error("Erro a carregar contas: " + (err.response?.data?.message || err.message));
      console.error("Erro a carregar contas:", err);
    } finally {
      setLoading(false);
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

  const handleAddAccount = async () => {
    try {
      setLoading(true);
      const response = await api.post("/api/citius-accounts/", newAccount);
      setAccounts([...accounts, response.data]);
      setNewAccount({
        username: "",
        password: "",
        advogado: "",
        email: "",
        is_active: true,
      });
      setShowAddForm(false);
      toast.success("Conta adicionada com sucesso!");
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
                onClick={() => setShowAddForm(!showAddForm)}
                className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {showAddForm ? (
                  <X size={16} className="mr-2" />
                ) : (
                  <Plus size={16} className="mr-2" />
                )}
                {showAddForm ? "Cancel" : "Adicionar Nova Conta"}
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
                Dismiss
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
                Add New Account
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
                    placeholder="Lawyer name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    E-mail
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
                <div className="flex items-center mt-6">
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
                    Active
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
                  Test Connection
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
                  Save Account
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
                      E-mail
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Used
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ações
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {accounts.map((account) => (
                    <tr key={account.id}>
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
                          account.email
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
                              Active
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
                            {account.is_active ? "Active" : "Inactive"}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {account.last_used
                          ? new Date(account.last_used).toLocaleString()
                          : "Never"}
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
