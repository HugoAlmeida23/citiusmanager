import { useState, useEffect } from "react";
import "../styles/Header.css";
import simpleLogo from "../assets/simplelogo.png";
import "@fortawesome/fontawesome-free/css/all.min.css";

function Header() {
  const [collapsed, setCollapsed] = useState(true); // Sidebar collapsed by default
  const [isMobile, setIsMobile] = useState(false);

  // Check if viewing on mobile device
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    // Initial check
    checkMobile();
    
    // Add event listener for window resize
    window.addEventListener('resize', checkMobile);
    
    // Cleanup
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Expand the sidebar when hovering (desktop only)
  const handleMouseEnter = () => {
    if (!isMobile) {
      setCollapsed(false);
    }
  };

  // Collapse the sidebar when mouse leaves (desktop only)
  const handleMouseLeave = () => {
    if (!isMobile) {
      setCollapsed(true);
    }
  };

  // Toggle sidebar for mobile
  const toggleSidebar = () => {
    setCollapsed(!collapsed);
  };

  return (
    <div className={`sidebar-container ${collapsed ? "collapsed" : ""} ${isMobile ? "mobile" : ""}`}>
      {/* Mobile toggle button */}
      {isMobile && (
        <button 
          className="mobile-toggle-btn" 
          onClick={toggleSidebar}
          aria-label={collapsed ? "Open sidebar" : "Close sidebar"}
        >
          <i className={`fas ${collapsed ? "fa-bars" : "fa-times"}`}></i>
        </button>
      )}
      
      {/* Sidebar overlay for mobile - closes sidebar when clicking outside */}
      {isMobile && !collapsed && (
        <div className="sidebar-overlay" onClick={toggleSidebar}></div>
      )}
      
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
            <a href="./" onClick={isMobile ? toggleSidebar : undefined}>
              <span className="icon fas fa-chart-bar text-white"></span>
              <span className="item-name">Notificações</span>
            </a>
            <div className="tooltip">Notificações</div>
          </li>
          <li>
            <a href="./accounts" onClick={isMobile ? toggleSidebar : undefined}>
              <span className="icon fas fa-user-circle text-white"></span>
              <span className="item-name">Contas</span>
            </a>
            <div className="tooltip">Contas</div>
          </li>
          <li>
            <a href="./audio-transcription" onClick={isMobile ? toggleSidebar : undefined}>
              <span className="icon fas fa-file-audio text-white"></span>
              <span className="item-name">Transcrição</span>
            </a>
            <div className="tooltip">Transcrição</div>
          </li>
          <li>
            <a href="./logout" onClick={isMobile ? toggleSidebar : undefined}>
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