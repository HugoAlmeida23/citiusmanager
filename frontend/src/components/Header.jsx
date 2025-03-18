import { useState } from "react";
import "../styles/Header.css";
import simpleLogo from "../assets/simplelogo.png";
import "@fortawesome/fontawesome-free/css/all.min.css";

function Header() {
  const [collapsed, setCollapsed] = useState(true); // Sidebar collapsed by default

  // Expand the sidebar when hovering
  const handleMouseEnter = () => {
    setCollapsed(false);
  };

  // Collapse the sidebar when mouse leaves
  const handleMouseLeave = () => {
    setCollapsed(true);
  };

  return (
    <div className={collapsed ? "collapsed" : ""}>
      <aside onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
        <a href="/" className="logo-wrapper">
          <img
            src={simpleLogo}
            alt="UI Kit Logo"
            style={{ width: "24px", height: "24px" }}
          />
          <span className="brand-name">Citius Manager</span>
        </a>

        <div className="separator"></div>

        <ul className="menu-items">
          <li>
            <a href="./">
              <span className="icon fas fa-chart-bar text-white"></span>
              <span className="item-name">Notificações</span>
            </a>
            <div className="tooltip">Notificações</div>
          </li>
          <li>
            <a href="./accounts">
              <span className="icon fas fa-user-circle text-white"></span>
              <span className="item-name">Contas</span>
            </a>
            <div className="tooltip">Contas</div>
          </li>
          <li>
            <a href="./audio-transcription">
              <span className="icon fas fa-file-audio text-white"></span>
              <span className="item-name">Transcrição</span>
            </a>
            <div className="tooltip">Transcrição</div>
          </li>
          <li>
            <a href="./logout">
              <span className="icon fa-solid fa-arrow-right-from-bracket text-white"></span>
              <span className="item-name">Sair</span>
            </a>
            <div className="tooltip">Sair</div>
          </li>
        </ul>
      </aside>
    </div>
  );
}

export default Header;
