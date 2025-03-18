import { useState, useRef } from "react";
import api from "../api"; // Adjust this import path to match your project structure
import Header from "../components/Header";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

function AudioTranscription() {
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [transcription, setTranscription] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setFileName(selectedFile.name);
      setError("");
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];

    if (
      droppedFile &&
      (droppedFile.type.includes("audio") ||
        droppedFile.name.endsWith(".m4a") ||
        droppedFile.name.endsWith(".mp3") ||
        droppedFile.name.endsWith(".wav"))
    ) {
      setFile(droppedFile);
      setFileName(droppedFile.name);
      setError("");
    } else {
      setError("Utilize um ficheiro de áudio válido! (.mp3, .m4a, .wav)");
      toast.error("Utilize um ficheiro de áudio válido! (.mp3, .m4a, .wav)");
    }
  };

  const handleSubmit = () => {
    if (!file) {
      setError("Utilize um ficheiro de áudio válido!");
      toast.error("Utilize um ficheiro de áudio válido!");
      return;
    }

    setIsLoading(true);
    setError("");

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
        toast.success("Transcrição Completa!");
      })
      .catch((err) => {
        console.error("Error:", err);
        setIsLoading(false);
        setError(
          err.response?.data?.error || `An error occurred: ${err.message}`
        );
        toast.error(
          err.response?.data?.error || `Ocorreu um erro: ${err.message}`
        );
      });
  };

  const handleDownload = () => {
    if (!transcription) return;

    const blob = new Blob([transcription], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcrição.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Download da transcrição feita com sucesso!");
  };

  const handleReset = () => {
    setFile(null);
    setFileName("");
    setTranscription("");
    setError("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    toast.info("Pronto para outro ficheiro!");
  };

  return (
    <div className="main">
      <Header />
      <div className="max-w-3xl mx-auto p-6">
        <div
          className="bg-white rounded-lg shadow-lg p-6"
          style={{ marginLeft: "5%", marginRight: "5%", marginTop: "5%" }}
        >
          <h1 className="text-2xl font-bold text-center mb-6">
            Conversão de Áudio para Texto
          </h1>

          {!transcription ? (
            <>
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-6 mb-4 text-center"
                onDragOver={handleDragOver}
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
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-12 w-12 text-gray-400 mb-3"
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
                    <p className="mb-2 text-sm text-gray-500">
                      <span className="font-semibold">Clica para inserir</span>{" "}
                      ou arrasta para aqui
                    </p>
                    <p className="text-xs text-gray-500">
                      MP3, M4A, WAV ficheiros suportados
                    </p>
                  </div>
                </label>

                {fileName && (
                  <div className="mt-4 p-2 bg-gray-100 rounded flex items-center justify-between">
                    <span className="text-sm truncate max-w-xs">
                      {fileName}
                    </span>
                    <button
                      onClick={handleReset}
                      className="text-red-500 hover:text-red-700"
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
                <div className="text-red-500 text-sm mb-4">{error}</div>
              )}

              <button
                onClick={handleSubmit}
                disabled={isLoading || !file}
                className={`w-full py-2 px-4 rounded font-medium ${
                  isLoading || !file
                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {isLoading ? "Transcribing..." : "Transcribe Audio"}
              </button>
            </>
          ) : (
            <div className="mt-6">
              <h2 className="text-xl font-semibold mb-3">
                Resultado da transcrição:{" "}
              </h2>
              <div className="bg-gray-50 p-4 rounded border border-gray-200 mb-4 max-h-80 overflow-y-auto whitespace-pre-wrap">
                {transcription}
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={handleDownload}
                  className="bg-green-600 text-white py-2 px-4 rounded font-medium hover:bg-green-700"
                >
                  Descarregar como ficheiro de texto
                </button>

                <button
                  onClick={handleReset}
                  className="bg-gray-200 text-gray-800 py-2 px-4 rounded font-medium hover:bg-gray-300"
                >
                  Inserir outro ficheiro
                </button>
              </div>
            </div>
          )}

          {isLoading && (
            <div className="mt-6 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
              <p className="mt-2 text-gray-600">A processar o ficheiro...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AudioTranscription;
