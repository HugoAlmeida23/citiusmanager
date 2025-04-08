import { useState, useRef, useEffect } from "react";
import api from "../api"; // Adjust this import path to match your project structure
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

function AudioTranscription() {
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [transcription, setTranscription] = useState("");
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);
  const [transcriptionTime, setTranscriptionTime] = useState(null);

  // Simulate progress during loading
  useEffect(() => {
    let interval;
    if (isLoading) {
      interval = setInterval(() => {
        setProgress((prev) => {
          const newProgress = prev + Math.random() * 2;
          if (newProgress >= 98) {
            clearInterval(interval);
            return 98; // Hold at 98% until complete
          }
          return newProgress;
        });
      }, 300);
    } else if (progress > 0 && progress < 100) {
      setProgress(100); // Complete the progress bar
      setTimeout(() => setProgress(0), 1000); // Reset after animation
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (validateAudioFile(selectedFile)) {
        setFile(selectedFile);
        setFileName(selectedFile.name);
        setError("");
      } else {
        showErrorMessage();
      }
    }
  };

  const validateAudioFile = (file) => {
    return (
      file.type.includes("audio") ||
      file.name.endsWith(".m4a") ||
      file.name.endsWith(".mp3") ||
      file.name.endsWith(".wav")
    );
  };

  const showErrorMessage = () => {
    const errorMsg = "Por favor utilize um ficheiro de áudio válido (.mp3, .m4a, .wav)";
    setError(errorMsg);
    toast.error(errorMsg);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const droppedFile = e.dataTransfer.files[0];

    if (droppedFile && validateAudioFile(droppedFile)) {
      setFile(droppedFile);
      setFileName(droppedFile.name);
      setError("");
    } else {
      showErrorMessage();
    }
  };

  const handleSubmit = () => {
    if (!file) {
      showErrorMessage();
      return;
    }

    setIsLoading(true);
    setError("");
    setProgress(0);
    const startTime = new Date();

    const formData = new FormData();
    formData.append("audio_file", file);

    api
      .post("/api/upload/", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      })
      .then((response) => {
        setTranscription(response.data.transcription);
        setIsLoading(false);
        const endTime = new Date();
        const processingTime = ((endTime - startTime) / 1000).toFixed(1);
        setTranscriptionTime(processingTime);
        toast.success("Transcrição Completa!");
      })
      .catch((err) => {
        console.error("Error:", err);
        setIsLoading(false);
        const errorMessage = err.response?.data?.error || `Ocorreu um erro: ${err.message}`;
        setError(errorMessage);
        toast.error(errorMessage);
      });
  };

  const handleDownload = () => {
    if (!transcription) return;

    const blob = new Blob([transcription], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcrição_${fileName.split('.')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Transcrição transferida com sucesso!");
  };

  const handleCopyToClipboard = () => {
    if (!transcription) return;
    
    navigator.clipboard.writeText(transcription)
      .then(() => toast.success("Texto copiado para a área de transferência!"))
      .catch(() => toast.error("Falha ao copiar o texto"));
  };

  const handleReset = () => {
    setFile(null);
    setFileName("");
    setTranscription("");
    setError("");
    setTranscriptionTime(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    toast.info("Pronto para outro ficheiro!");
  };

  const getFileSize = () => {
    if (!file) return "";
    const size = file.size / 1024 / 1024; // Convert to MB
    return size.toFixed(2) + " MB";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* CSS for basic animations without framer-motion */}
      <style jsx>{`
        .fade-in {
          animation: fadeIn 0.5s ease-in-out;
        }
        
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        .slide-in {
          animation: slideIn 0.5s ease-in-out;
        }
        
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div className="max-w-5xl mx-auto p-4 sm:p-6 lg:p-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-center mb-8">
          <div className="flex items-center mb-4 sm:mb-0">
            <div className="bg-blue-600 p-2 rounded-lg mr-3">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-800">AudioScribe</h1>
          </div>
          <div className="flex space-x-2">
            <button className="bg-white px-4 py-2 rounded-lg text-gray-600 font-medium shadow-sm hover:shadow-md transition">
              Documentação
            </button>
            <button className="bg-black px-4 py-2 rounded-lg text-white font-medium shadow-sm hover:bg-gray-800 transition">
              Iniciar Sessão
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="bg-white rounded-xl shadow-xl overflow-hidden"
        >
          {/* Content Header */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4 sm:px-8 sm:py-6">
            <h2 className="text-xl sm:text-2xl font-bold text-white">
              Conversão de Áudio para Texto
            </h2>
            <p className="text-blue-100 mt-1">
              Transcreva os seus ficheiros de áudio com precisão em segundos.
            </p>
          </div>

          <div className="p-6 sm:p-8">
            {/* Upload Section */}
            {!transcription ? (
              <>
                <div
                  className={`border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-all ${
                    dragActive 
                      ? "border-blue-500 bg-blue-50" 
                      : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
                  }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    accept=".mp3,.m4a,.wav,audio/*"
                    id="audio-file"
                  />

                  <label htmlFor="audio-file" className="cursor-pointer">
                    <div className="flex flex-col items-center justify-center">
                      <div className="bg-blue-100 p-4 rounded-full mb-4">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-10 w-10 text-blue-600"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                          />
                        </svg>
                      </div>
                      <h3 className="text-lg font-semibold text-gray-800 mb-2">
                        Selecione um ficheiro de áudio
                      </h3>
                      <p className="mb-2 text-gray-500">
                        <span className="font-medium">Clique para inserir</span> ou
                        arraste e solte o seu ficheiro aqui
                      </p>
                      <p className="text-sm text-gray-400">
                        MP3, M4A, WAV até 500 MB
                      </p>
                    </div>
                  </label>

                  {fileName && (
                    <div className="mt-6 p-4 bg-gray-50 rounded-lg flex items-center justify-between fade-in"
                    >
                      <div className="flex items-center">
                        <div className="bg-blue-100 p-2 rounded-md">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5 text-blue-600"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        </div>
                        <div className="ml-3">
                          <p className="text-sm font-medium text-gray-900 truncate max-w-xs">
                            {fileName}
                          </p>
                          <p className="text-xs text-gray-500">{getFileSize()}</p>
                        </div>
                      </div>
                      <button
                        onClick={handleReset}
                        className="text-gray-400 hover:text-red-500 transition"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-5 w-5"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                        >
                          <path
                            fillRule="evenodd"
                            d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6 flex items-start fade-in"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-5 w-5 mr-2 mt-0.5 flex-shrink-0"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        fillRule="evenodd"
                        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span>{error}</span>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <div className="flex items-center text-gray-500 text-sm">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4 mr-1"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    Transcreva ficheiros em português de Portugal, Brasil e mais 50 idiomas
                  </div>
                  <button
                    onClick={handleSubmit}
                    disabled={isLoading || !file}
                    className={`flex items-center justify-center py-3 px-6 rounded-lg font-medium shadow-sm transition ${
                      isLoading || !file
                        ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                        : "bg-blue-600 text-white hover:bg-blue-700 hover:shadow"
                    }`}
                  >
                    {isLoading ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        A processar...
                      </>
                    ) : (
                      <>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-5 w-5 mr-2"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        Transcrever Áudio
                      </>
                    )}
                  </button>
                </div>
              </>
            ) : (
              <div className="mt-2 fade-in"
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-gray-800">
                    Resultado da Transcrição
                  </h2>
                  {transcriptionTime && (
                    <div className="text-sm text-gray-500 flex items-center">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4 mr-1"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      Processado em {transcriptionTime} segundos
                    </div>
                  )}
                </div>
                <div className="bg-gray-50 p-6 rounded-lg border border-gray-200 mb-6 max-h-96 overflow-y-auto whitespace-pre-wrap text-gray-700">
                  {transcription}
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={handleDownload}
                    className="flex items-center bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 transition shadow-sm hover:shadow"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-5 w-5 mr-2"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                    Transferir Ficheiro
                  </button>

                  <button
                    onClick={handleCopyToClipboard}
                    className="flex items-center bg-white border border-gray-300 text-gray-700 py-3 px-6 rounded-lg font-medium hover:bg-gray-50 transition shadow-sm hover:shadow"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-5 w-5 mr-2"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                      />
                    </svg>
                    Copiar para Área de Transferência
                  </button>

                  <button
                    onClick={handleReset}
                    className="flex items-center bg-gray-100 text-gray-700 py-3 px-6 rounded-lg font-medium hover:bg-gray-200 transition"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-5 w-5 mr-2"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      />
                    </svg>
                    Inserir Outro Ficheiro
                  </button>
                </div>
              </div>
            )}

            {isLoading && (
              <div className="mt-8 fade-in"
              >
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium text-gray-700">A processar o ficheiro...</h3>
                  <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
                <div className="text-sm text-gray-500 italic text-center animate-pulse">
                  Este processo pode demorar alguns minutos dependendo do tamanho do ficheiro
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Features Section */}
        {!isLoading && !transcription && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10 fade-in"
          >
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <div className="bg-blue-100 p-3 rounded-lg inline-block mb-3">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6 text-blue-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Vários Idiomas</h3>
              <p className="text-gray-600">
                Transcreva áudio em mais de 50 idiomas diferentes, incluindo vários sotaques regionais.
              </p>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm">
              <div className="bg-blue-100 p-3 rounded-lg inline-block mb-3">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6 text-blue-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Alta Precisão</h3>
              <p className="text-gray-600">
                Tecnologia de IA avançada para garantir transcrições precisas mesmo em ambientes ruidosos.
              </p>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm">
              <div className="bg-blue-100 p-3 rounded-lg inline-block mb-3">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6 text-blue-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Processamento Rápido</h3>
              <p className="text-gray-600">
                Transcreva horas de áudio em minutos, poupando tempo e aumentando a produtividade.
              </p>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-12 text-center text-gray-500 text-sm">
          <p>© 2025 AudioScribe. Todos os direitos reservados.</p>
        </div>
      </div>
    </div>
  );
}

export default AudioTranscription;