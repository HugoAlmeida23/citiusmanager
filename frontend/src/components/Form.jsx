import React, { useState } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";
import logo from "../assets/simplelogo.png";
import "../styles/ModernForm.css";
import { toast } from "react-toastify";  // Import toast
import "react-toastify/dist/ReactToastify.css"; // Import toast styles


const ModernForm = ({ route, method }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const name = method === "login" ? "Login" : "Register";

  // Function to display success notification
  const notifySuccess = (message) => toast.success(message);

  // Function to display error notification
  const notifyError = (message) => toast.error(message);

  const handleSubmit = async (e) => {
    setLoading(true);
    e.preventDefault();

    try {
      const res = await api.post(route, { username, password });
      if (method === "login") {
        localStorage.setItem(ACCESS_TOKEN, res.data.access);
        localStorage.setItem(REFRESH_TOKEN, res.data.refresh);
        notifySuccess("Login feito com sucesso! Bem-Vindo.");
        navigate("/");
      } else {
        notifySuccess("Registro feito com sucesso! Por favor faça o login.");
        navigate("/login");
      }
    } catch (error) {
      if (error.response && error.response.data) {
        notifyError("Autenticação falhou. Tente novamente.");
      } else {
        notifyError("Autenticação falhou. Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="form-container">
      <div className="form-card">
        <div className="form-header">
          <img src={logo} alt="Logo" className="logo" />
          <h1>{name}</h1>
        </div>

        <form onSubmit={handleSubmit} className="form-body">
          <div className="input-field">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
            />
          </div>

          <div className="input-field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          <button type="submit" disabled={loading} className={`submit-btn ${loading ? "loading" : ""}`}>
            {loading ? (
              <div className="loader"></div>
            ) : (
              name
            )}
          </button>

          <div className="footer-text">
            {method === "login" ? (
              <p>
                Don't have an account?{" "}
                <span onClick={() => navigate("/register")} className="link-text">
                  Register
                </span>
              </p>
            ) : (
              <p>
                Already have an account?{" "}
                <span onClick={() => navigate("/login")} className="link-text">
                  Login
                </span>
              </p>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default ModernForm;