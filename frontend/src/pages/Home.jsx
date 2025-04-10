import React, { useState, useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Filter,
  FilterX,
  Search,
  Settings,
} from "lucide-react";
import "../styles/Home.css";
import Header from "../components/Header";
import api from "../api";
import NotificationsComponent from "../components/NotificationsReload";

const LegalNotificationsDashboard = () => {
  const [notificacoes, setNotificacoes] = useState([]);
  const [filteredNotificacoes, setFilteredNotificacoes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filters, setFilters] = useState({
    advogado: "",
    origem: "",
    data: "",
    tribunal: "",
    especie: "",
    unidade: "",
  });
  const [currentPage, setCurrentPage] = useState(0);
  const [filtersVisible, setFiltersVisible] = useState(false);
  const [columnSettingsVisible, setColumnSettingsVisible] = useState(false);
  const itemsPerPage = 5;

  // Configuração de colunas
  const allColumns = [
    { id: "advogado", label: "Responsável", visible: true },
    { id: "origem", label: "Origem", visible: true },
    { id: "data", label: "Data Elaboração", visible: true },
    { id: "acto", label: "Acto", visible: true },
    { id: "tribunal", label: "Tribunal", visible: true },
    { id: "unidade", label: "Un. Orgânica", visible: true },
    { id: "processo", label: "Processo", visible: true },
    { id: "especie", label: "Espécie", visible: true },
    { id: "referencia", label: "Referência", visible: true },
  ];

  const [visibleColumns, setVisibleColumns] = useState(allColumns);

  useEffect(() => {
    fetchProcessos();
  }, []);

  const fetchProcessos = () => {
    setLoading(true);
    api
      .get("/api/processos/")
      .then((res) => {
        const sortedData = [...res.data].sort((a, b) => {
          const dateA = parseDate(a.data);
          const dateB = parseDate(b.data);
          return dateB - dateA;
        });
        setNotificacoes(sortedData);
        setFilteredNotificacoes(sortedData);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching data:", err);
        setLoading(false);
      });
  };

  // Parse date in "DD-MM-YYYY" format to Date object
  const parseDate = (dateStr) => {
    if (!dateStr) return new Date(0); // Handle empty dates
    const [day, month, year] = dateStr.split("-");
    return new Date(`${year}-${month}-${day}`);
  };

  // Get the most common item from an array of objects for a specific field
  const getMostCommon = (field) => {
    if (!notificacoes.length) return "N/A";

    // Count occurrences
    const counts = notificacoes.reduce((acc, item) => {
      const value = item[field];
      if (!value) return acc;

      acc[value] = (acc[value] || 0) + 1;
      return acc;
    }, {});

    // Find the most common value
    let maxCount = 0;
    let mostCommon = "N/A";

    Object.entries(counts).forEach(([value, count]) => {
      if (count > maxCount) {
        maxCount = count;
        mostCommon = value;
      }
    });

    return mostCommon;
  };

  // Extract unique values for filter dropdowns
  const getUniqueValues = (field) => {
    const values = [
      ...new Set(notificacoes.map((item) => item[field]).filter(Boolean)),
    ];
    return values.sort();
  };

  const advogados = getUniqueValues("advogado");
  const origens = getUniqueValues("origem");
  const tribunais = getUniqueValues("tribunal");
  const especies = getUniqueValues("especie");
  const unidades = getUniqueValues("unidade");

  // Safely handle date sorting
  const datas = getUniqueValues("data").sort((a, b) => {
    try {
      return parseDate(b) - parseDate(a);
    } catch (error) {
      return 0;
    }
  });

  // Calculate paginated data
  const paginatedData = filteredNotificacoes.slice(
    currentPage * itemsPerPage,
    (currentPage + 1) * itemsPerPage
  );

  // Apply filters and search
  useEffect(() => {
    let results = [...notificacoes];

    // Apply all active filters
    Object.entries(filters).forEach(([key, value]) => {
      if (value) {
        results = results.filter((item) => item[key] === value);
      }
    });

    // Apply search term across all fields
    if (searchTerm) {
      const search = searchTerm.toLowerCase().trim();
      results = results.filter((item) =>
        Object.entries(item).some(
          ([key, val]) =>
            val && typeof val === "string" && val.toLowerCase().includes(search)
        )
      );
    }

    setFilteredNotificacoes(results);
    setCurrentPage(0); // Reset to first page when filters change
  }, [filters, searchTerm, notificacoes]);

  // Handle filter changes
  const handleFilterChange = (field, value) => {
    setFilters((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({
      advogado: "",
      origem: "",
      data: "",
      tribunal: "",
      especie: "",
      unidade: "",
    });
    setSearchTerm("");
  };

  // Get most recent notification date
  const getMostRecentDate = () => {
    if (datas.length === 0) return "N/A";
    return datas[0];
  };

  // Total pages calculation
  const totalPages = Math.ceil(filteredNotificacoes.length / itemsPerPage);

  // Toggle column visibility
  const toggleColumnVisibility = (columnId) => {
    setVisibleColumns((prev) =>
      prev.map((col) =>
        col.id === columnId ? { ...col, visible: !col.visible } : col
      )
    );
  };

  // Show all columns
  const showAllColumns = () => {
    setVisibleColumns((prev) => prev.map((col) => ({ ...col, visible: true })));
  };

  // Hide all columns (except at least one)
  const hideAllColumns = () => {
    const updatedColumns = [...visibleColumns];
    const atLeastOneVisible = updatedColumns.some((col) => col.visible);

    if (atLeastOneVisible) {
      setVisibleColumns(
        updatedColumns.map((col, index) =>
          index === 0 ? { ...col, visible: true } : { ...col, visible: false }
        )
      );
    }
  };

  // Save column configuration
  const saveColumnConfiguration = () => {
    // Here you could save the configuration to localStorage or a backend
    setColumnSettingsVisible(false);
    // Optional: localStorage.setItem('tableColumns', JSON.stringify(visibleColumns));
  };

  return (
    <div className="main">
      <Header />
      <div
        className="p-6 bg-gray-100 min-h-screen"
        style={{ marginLeft: "3%" }}
      >
        <header className="bg-blue-800 text-white p-4 rounded-t-lg shadow flex justify-between items-center">
          <h1 className="text-2xl text-white font-bold">
            Notificações Judiciais
          </h1>
          <div className="flex items-center">
            <NotificationsComponent onRefreshComplete={fetchProcessos} />
          </div>
        </header>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 my-4">
          <div
            className="bg-white p-4 rounded-lg shadow"
            role="region"
            aria-label="Estatísticas de notificações"
          >
            <h3 className="text-lg font-semibold text-gray-600">
              Total de Notificações
            </h3>
            <p className="text-3xl font-bold text-blue-800">
              {filteredNotificacoes.length}
            </p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-600">
              Origem Mais Comum
            </h3>
            <p className="text-3xl font-bold text-blue-800">
              {getMostCommon("origem")}
            </p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-600">
              Notificação Mais Recente
            </h3>
            <p className="text-3xl font-bold text-blue-800">
              {getMostRecentDate()}
            </p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="text-lg font-semibold text-gray-600">
              Tribunal Mais Frequente
            </h3>
            <p className="text-xl font-bold text-blue-800">
              {getMostCommon("tribunal")}
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="bg-white p-4 rounded-lg shadow mb-4">
          <div className="flex flex-col md:flex-row gap-4 mb-4">
            <button
              onClick={() => setFiltersVisible(!filtersVisible)}
              className="filter-button"
            >
              {filtersVisible ? (
                <FilterX className="filter-icon" />
              ) : (
                <Filter className="filter-icon" />
              )}
            </button>
            <div className="flex-1 relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search size={16} className="text-gray-400" />
              </div>
              <input
                type="text"
                className="w-full pl-10 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Pesquisar em todos os campos..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                aria-label="Pesquisar notificações"
              />
            </div>
            <button
              onClick={clearFilters}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-75 cursor-pointer"
              aria-label="Limpar todos os filtros"
            >
              Limpar Filtros
            </button>
            <button
              onClick={() => setColumnSettingsVisible(!columnSettingsVisible)}
              className="settings-button"
              aria-label="Personalizar colunas da tabela"
            >
              <Settings size={16} className="settings-icon" />
              <span>Personalizar Tabela</span>
            </button>
          </div>

          {/* Filters - can be toggled */}
          {filtersVisible && (
            <div
              className="grid grid-cols-1 md:grid-cols-3 gap-4"
              role="region"
              aria-label="Filtros de notificações"
            >
              {[
                { label: "Responsável", field: "advogado", options: advogados },
                { label: "Origem", field: "origem", options: origens },
                { label: "Data Elaboração", field: "data", options: datas },
                { label: "Tribunal", field: "tribunal", options: tribunais },
                { label: "Espécie", field: "especie", options: especies },
                { label: "Unidade", field: "unidade", options: unidades },
              ].map((filter, idx) => (
                <div key={idx} className="mb-2">
                  <label
                    htmlFor={`filter-${filter.field}`}
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {filter.label}
                  </label>
                  <select
                    id={`filter-${filter.field}`}
                    className="w-full p-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={filters[filter.field]}
                    onChange={(e) =>
                      handleFilterChange(filter.field, e.target.value)
                    }
                    aria-label={`Filtrar por ${filter.label}`}
                  >
                    <option value="">Todos</option>
                    {filter.options.map((option, optIdx) => (
                      <option key={optIdx} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          )}

          {/* Column Settings - can be toggled */}
          {columnSettingsVisible && (
            <div className="mt-4 bg-gray-50 p-4 rounded-md border border-gray-200">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-lg font-medium text-gray-800">
                  Personalizar Colunas
                </h3>
                <div className="flex space-x-2">
                  <button
                    onClick={showAllColumns}
                    className="px-2 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                  >
                    Mostrar Todas
                  </button>
                  <button
                    onClick={hideAllColumns}
                    className="px-2 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
                  >
                    Ocultar Todas
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {visibleColumns.map((column) => (
                  <div key={column.id} className="flex items-center">
                    <input
                      type="checkbox"
                      id={`column-${column.id}`}
                      checked={column.visible}
                      onChange={() => toggleColumnVisibility(column.id)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label
                      htmlFor={`column-${column.id}`}
                      className="ml-2 block text-sm text-gray-700"
                    >
                      {column.label}
                    </label>
                  </div>
                ))}
              </div>
              <div className="flex justify-end mt-4">
                <button
                  onClick={saveColumnConfiguration}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  Aplicar Alterações
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Pagination Controls */}
        <div className="flex space-x-2 items-center mb-2">
          <button
            onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
            disabled={currentPage === 0}
            className="px-4 py-2 border rounded-md bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            aria-label="Página anterior"
          >
            <ChevronLeft size={16} className="mr-1" />
            Anterior
          </button>

          <span className="text-sm text-gray-600">
            Página {currentPage + 1} de {Math.max(1, totalPages)}
          </span>

          <button
            onClick={() =>
              setCurrentPage(Math.min(totalPages - 1, currentPage + 1))
            }
            disabled={currentPage >= totalPages - 1}
            className="px-4 py-2 border rounded-md bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            aria-label="Próxima página"
          >
            Próximo
            <ChevronRight size={16} className="ml-1" />
          </button>
        </div>

        {/* Data Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {loading ? (
            <div className="flex justify-center items-center p-8">
              <div
                className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"
                aria-label="Carregando..."
              ></div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table
                className="w-full table-auto"
                aria-label="Tabela de notificações judiciais"
              >
                <thead className="bg-gray-50">
                  <tr>
                    {visibleColumns
                      .filter((column) => column.visible)
                      .map((column, idx) => (
                        <th
                          key={idx}
                          scope="col"
                          className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                        >
                          {column.label}
                        </th>
                      ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredNotificacoes.length > 0 ? (
                    paginatedData.map((item, index) => (
                      <tr
                        key={index}
                        className={
                          index % 2 === 0
                            ? "bg-white hover:bg-gray-50"
                            : "bg-gray-50 hover:bg-gray-100"
                        }
                      >
                        {visibleColumns
                          .filter((column) => column.visible)
                          .map((column, colIdx) => (
                            <td
                              key={colIdx}
                              className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                            >
                              {item[column.id] || "-"}
                            </td>
                          ))}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td
                        colSpan={
                          visibleColumns.filter((col) => col.visible).length
                        }
                        className="px-6 py-8 text-center text-sm text-gray-500"
                      >
                        Nenhuma notificação encontrada
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination Info */}
        {!loading && filteredNotificacoes.length > 0 && (
          <div className="flex justify-between items-center mt-4 bg-white p-4 rounded-lg shadow">
            <div
              className="text-sm text-gray-700"
              role="status"
              aria-live="polite"
            >
              Mostrando {currentPage * itemsPerPage + 1} a{" "}
              {Math.min(
                (currentPage + 1) * itemsPerPage,
                filteredNotificacoes.length
              )}{" "}
              de {filteredNotificacoes.length} resultados
            </div>
          </div>
        )}

        {/* Accessibility Skip Link - hidden visually but available for screen readers */}
        <a
          href="#top"
          className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:p-2 focus:bg-blue-800 focus:text-white focus:z-50"
        >
          Voltar ao topo
        </a>
      </div>
    </div>
  );
};

export default LegalNotificationsDashboard;
