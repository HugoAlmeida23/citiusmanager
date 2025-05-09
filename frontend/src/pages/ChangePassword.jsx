import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Header from "../components/Header";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import "../styles/ModernForm.css";

const ChangePassword = () => {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Function to display notifications
  const notifySuccess = (message) => toast.success(message);
  const notifyError = (message) => toast.error(message);
  const notifyWarning = (message) => toast.warning(message);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate passwords
    if (newPassword !== confirmPassword) {
      notifyWarning("As senhas não coincidem. Por favor, tente novamente.");
      return;
    }
    
    // Check password strength
    if (newPassword.length < 8) {
      notifyWarning("A nova senha deve ter pelo menos 8 caracteres.");
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await api.post("/api/change-password/", {
        current_password: currentPassword,
        new_password: newPassword
      });
      
      notifySuccess("Senha alterada com sucesso!");
      // Clear the form
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      
      // Redirect to home page after short delay
      setTimeout(() => {
        navigate("/");
      }, 2000);
      
    } catch (error) {
      console.error("Error changing password:", error);
      
      if (error.response && error.response.data) {
        // Handle specific error messages from backend
        if (error.response.data.current_password) {
          notifyError("Senha atual incorreta.");
        } else if (error.response.data.detail) {
          notifyError(error.response.data.detail);
        } else {
          notifyError("Erro ao alterar senha. Por favor, tente novamente.");
        }
      } else {
        notifyError("Erro ao alterar senha. Por favor, tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main">
      <Header />
      <div className="form-container" style={{ marginLeft: "3%" }}>
        <div className="form-card">
          <div className="form-header">
            <h1>Alterar Senha</h1>
            <p className="form-subtitle">Atualize suas credenciais de acesso</p>
          </div>

          <form onSubmit={handleSubmit} className="form-body">
            <div className="input-field">
              <label>Senha Atual</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Digite sua senha atual"
                required
              />
            </div>

            <div className="input-field">
              <label>Nova Senha</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Digite sua nova senha"
                required
              />
            </div>

            <div className="input-field">
              <label>Confirmar Nova Senha</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirme sua nova senha"
                required
              />
            </div>

            <div className="password-requirements">
              <p>A senha deve ter pelo menos 8 caracteres.</p>
            </div>

            <button 
              type="submit" 
              disabled={loading} 
              className={`submit-btn ${loading ? "loading" : ""}`}
            >
              {loading ? (
                <div className="loader"></div>
              ) : (
                "Alterar Senha"
              )}
            </button>

            <div className="footer-text">
              <p>
                <span onClick={() => navigate("/")} className="link-text">
                  Voltar para página inicial
                </span>
              </p>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChangePassword;