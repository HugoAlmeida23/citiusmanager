
import { useState, useRef, useEffect } from "react";
import api from "../api";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import Header from "../components/Header";
import { jsPDF } from "jspdf";
import "jspdf-autotable";

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
  const [transcriptionData, setTranscriptionData] = useState(null); // For JSON format
  const [formatType, setFormatType] = useState("json"); // Default to text formatconst [transcriptionData, setTranscriptionData] = useState(null); // For JSON format
  const [speakerNames, setSpeakerNames] = useState({}); // Para armazenar os nomes personalizados dos falantes
  const [editingNames, setEditingNames] = useState(false); // Controla se está editando os nomes dos falantes

  // New state variables for async processing
  const [jobId, setJobId] = useState(null);
  const [pollingInterval, setPollingInterval] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [startTime, setStartTime] = useState(null);

  const [editableTranscription, setEditableTranscription] = useState(null);
  const [isEditing, setIsEditing] = useState(false);

  // Adicionar este useEffect para inicializar a versão editável
  useEffect(() => {
    if (transcriptionData && transcriptionData.utterances) {
      setEditableTranscription(JSON.parse(JSON.stringify(transcriptionData)));
    }
  }, [transcriptionData]);

  // Simulate progress during loading for small files
  useEffect(() => {
    let interval;
    if (isLoading && !isPolling) {
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
    } else if (progress > 0 && progress < 100 && !isPolling) {
      setProgress(100); // Complete the progress bar
      setTimeout(() => setProgress(0), 1000); // Reset after animation
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading, isPolling]);

  // Cleanup polling when component unmounts
  // Make sure the polling effect doesn't depend on isPolling
  // This effect cleans up polling when the component unmounts
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        console.log('Component unmounting, clearing polling interval');
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]); // Only depend on pollingInterval, not isPolling

  // Add a new effect to monitor isPolling state changes for debugging
  useEffect(() => {
    console.log('isPolling state changed to:', isPolling);
  }, [isPolling]);

  // Inicializa os nomes dos falantes quando a transcrição é carregada
  useEffect(() => {
    if (transcriptionData && transcriptionData.utterances) {
      const uniqueSpeakers = [...new Set(transcriptionData.utterances.map(u => u.speaker))];
      const initialSpeakerNames = {};

      uniqueSpeakers.forEach(speaker => {
        initialSpeakerNames[speaker] = `Falante ${speaker}`;
      });

      setSpeakerNames(initialSpeakerNames);
    }
  }, [transcriptionData]);

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
      file.name.endsWith(".wav") ||
      file.name.endsWith(".ogg") ||
      file.name.endsWith(".flac")
    );
  };

  // Função para atualizar o texto de uma fala específica
  const updateUtteranceText = (index, newText) => {
    if (!editableTranscription) return;

    const newTranscription = { ...editableTranscription };
    newTranscription.utterances[index].text = newText;
    setEditableTranscription(newTranscription);
  };

  // Função para salvar as edições
  const saveTranscriptionEdits = () => {
    setTranscriptionData(editableTranscription);
    setIsEditing(false);
    toast.success("Edições salvas com sucesso!");
  };

  const removeUtterance = (index) => {
    if (!editableTranscription) return;

    const newTranscription = { ...editableTranscription };
    // Remove a fala no índice especificado
    newTranscription.utterances = newTranscription.utterances.filter((_, i) => i !== index);

    // Atualiza o texto completo da transcrição também
    if (newTranscription.text) {
      // Reconstruir o texto completo a partir das falas restantes
      newTranscription.text = newTranscription.utterances
        .map(u => `${speakerNames[u.speaker] || `Falante ${u.speaker}`}: ${u.text}`)
        .join('\n\n');
    }

    setEditableTranscription(newTranscription);
    toast.info("Fala removida");
  };

  // Função para iniciar a edição
  const startEditing = () => {
    setIsEditing(true);
    setEditingNames(false);
  };

  // Função para cancelar a edição
  const cancelEditing = () => {
    setEditableTranscription(JSON.parse(JSON.stringify(transcriptionData)));
    setIsEditing(false);
    toast.info("Edições canceladas");
  };

  const TranscriptEditor = () => {
    if (!editableTranscription || !editableTranscription.utterances) {
      return null;
    }

    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            Editar Transcrição
          </h3>
          <div className="flex gap-2">
            <button
              onClick={cancelEditing}
              className="px-3 py-1 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={saveTranscriptionEdits}
              className="px-3 py-1 bg-blue-600 rounded-md text-white hover:bg-blue-700 transition-colors"
            >
              Salvar Alterações
            </button>
          </div>
        </div>

        <div className="space-y-4 max-h-96 overflow-y-auto">
          {editableTranscription.utterances.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              Não há falas para exibir. Todas as falas foram removidas.
            </div>
          ) : (
            editableTranscription.utterances.map((utterance, index) => {
              const speakerName = speakerNames[utterance.speaker] || `Falante ${utterance.speaker}`;
              const timestamp = utterance.start !== undefined
                ? `[${formatTimestamp(utterance.start)}]`
                : "";

              return (
                <div key={index} className="p-3 bg-gray-50 rounded-md transition-all hover:shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center">
                      <span className="text-xs text-gray-500 mr-2">{timestamp}</span>
                      <span className="font-medium text-blue-600">{speakerName}:</span>
                    </div>
                    <button
                      onClick={() => removeUtterance(index)}
                      className="text-red-500 hover:text-red-700 p-1"
                      title="Remover esta fala"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M"></path>
                      </svg>
                    </button>
                  </div>
                  <textarea
                    value={utterance.text}
                    onChange={(e) => updateUtteranceText(index, e.target.value)}
                    className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    rows={Math.max(2, Math.ceil(utterance.text.length / 70))}
                  />
                </div>
              );
            })
          )}
        </div>
      </div>
    );
  };

  // Componente de visualização da transcrição
  const TranscriptionViewer = () => {
    if (!transcriptionData || !transcriptionData.utterances) {
      return null;
    }

    return (
      <div className="bg-gray-50 p-6 rounded-lg border border-gray-200 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-medium text-gray-900">Transcrição</h3>
          <button
            onClick={startEditing}
            className="flex items-center text-blue-600 hover:text-blue-800 transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 mr-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
              />
            </svg>
            Editar texto
          </button>
        </div>

        <div className="max-h-96 overflow-y-auto whitespace-pre-wrap text-gray-700">
          {transcriptionData.utterances.map((utterance, index) => (
            <div key={index} className="mb-3 pb-3 border-b border-gray-200 last:border-0">
              <div className="flex items-start">
                <span className="text-xs text-gray-500 mr-2 mt-1">
                  [{formatTimestamp(utterance.start)}]
                </span>
                <div>
                  <span className="font-bold text-blue-600">
                    {speakerNames[utterance.speaker] || `Falante ${utterance.speaker}`}:
                  </span>
                  <span> {utterance.text}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const showErrorMessage = () => {
    const errorMsg = "Por favor utilize um ficheiro de áudio válido (.mp3, .m4a, .wav, .ogg, .flac)";
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

  const pollForResults = (id) => {
    setIsPolling(true);

    console.log(`Starting to poll for job ID: ${id}`);

    // Add retry tracking
    let retryCount = 0;
    const maxRetries = 24; // 2 minutes (5s interval * 24 attempts = 120s)

    // Create the interval
    const intervalId = setInterval(() => {
      console.log(`Polling for status of job: ${id}, attempt ${retryCount + 1}`);

      // Use the job ID as indicator - if we have a valid job ID, keep polling
      if (!id) {
        console.log('No valid job ID, stopping polling');
        clearInterval(intervalId);
        setIsPolling(false);
        return;
      }

      // Check if we've exceeded maximum retries
      if (retryCount >= maxRetries) {
        console.log(`Exceeded maximum retries (${maxRetries}), stopping polling`);
        clearInterval(intervalId);
        setIsPolling(false);
        setIsLoading(false);
        setError("Tempo limite excedido ao aguardar pela transcrição. Tente novamente.");
        toast.error("Tempo limite excedido ao aguardar pela transcrição.");
        return;
      }

      api.get(`/api/transcription/status/${id}/`)
        .then((response) => {
          console.log('Polling response:', response.data);

          // Reset retry count on successful response
          retryCount = 0;

          // Update progress
          setProgress(response.data.progress || 0);
          console.log(`Progress: ${response.data.progress || 0}%`);

          // If completed, handle the result
          if (response.data.status === 'completed' && response.data.result) {
            console.log('Transcription completed!');
            clearInterval(intervalId);
            setIsPolling(false);
            setIsLoading(false);

            console.log('Result type:', typeof response.data.result);

            // Format the result appropriately
            if (formatType === "json" && typeof response.data.result === "object") {
              console.log('Setting JSON data');
              setTranscriptionData(response.data.result);
              setTranscription(response.data.result.text || JSON.stringify(response.data.result, null, 2));
            } else {
              console.log('Setting text data');
              setTranscription(response.data.result);
              setTranscriptionData(null);
            }

            const endTime = new Date();
            const processingTime = ((endTime - startTime) / 1000).toFixed(1);
            setTranscriptionTime(processingTime);
            toast.success("Transcrição Completa!");
          }

          // If failed, handle the error
          else if (response.data.status === 'failed') {
            console.log('Transcription failed:', response.data.error);
            clearInterval(intervalId);
            setIsPolling(false);
            setIsLoading(false);
            const errorMessage = response.data.error || "A transcrição falhou. Tente novamente.";
            setError(errorMessage);
            toast.error(errorMessage);
          }
          else {
            console.log(`Current status: ${response.data.status}, progress: ${response.data.progress}%`);
          }
        })
        .catch((err) => {
          console.error("Error polling for results:", err);

          // For 404 errors, increment retry count but don't stop polling yet
          if (err.response && err.response.status === 404) {
            retryCount++;
            console.log(`Job not found (404), retry attempt ${retryCount}/${maxRetries}`);
            toast.info(`Aguardando processamento do trabalho... (${retryCount}/${maxRetries})`, {
              autoClose: 2000,
              toastId: 'polling-retry'
            });
          } else {
            // For other errors, stop polling
            clearInterval(intervalId);
            setIsPolling(false);
            setIsLoading(false);
            setError("Erro ao verificar o estado da transcrição.");
            toast.error("Erro ao verificar o estado da transcrição.");
          }
        });
    }, 5000); // Poll every 5 seconds

    // Store the interval ID in state so we can clear it later
    setPollingInterval(intervalId);
  };

  // Update the handleSubmit function to ensure polling starts correctly
  const handleSubmit = () => {
    if (!file) {
      showErrorMessage();
      return;
    }

    setIsLoading(true);
    setError("");
    setProgress(0);
    setIsPolling(false); // Reset polling state first
    const newStartTime = new Date();
    setStartTime(newStartTime);

    const formData = new FormData();
    formData.append("audio_file", file);
    formData.append("format", formatType); // Add format parameter

    console.log("Submitting audio file for transcription...");

    api
      .post("/api/upload/", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      })
      .then((response) => {
        console.log("Upload response:", response.data);

        // Check if we received a job_id (async processing for large files)
        if (response.data.job_id) {
          console.log(`Received job_id: ${response.data.job_id}`);
          setJobId(response.data.job_id);

          // Clear any existing polling interval
          if (pollingInterval) {
            clearInterval(pollingInterval);
            setPollingInterval(null);
          }

          // Start polling for results with a slight delay to ensure backend is ready
          setTimeout(() => {
            console.log(`Starting polling for job_id: ${response.data.job_id}`);
            pollForResults(response.data.job_id);
          }, 1000);

          toast.info("Ficheiro grande detectado. A transcrição será processada em segundo plano.");
        } else {
          console.log("Received direct response (small file)");
          // Handle immediate response (small files)
          if (formatType === "json" && typeof response.data.transcription === "object") {
            setTranscriptionData(response.data.transcription);
            // Also set the text version for display
            setTranscription(response.data.transcription.text || JSON.stringify(response.data.transcription, null, 2));
          } else {
            setTranscription(response.data.transcription);
            setTranscriptionData(null);
          }

          setIsLoading(false);
          const endTime = new Date();
          const processingTime = ((endTime - newStartTime) / 1000).toFixed(1);
          setTranscriptionTime(processingTime);
          toast.success("Transcrição Completa!");
        }
      })
      .catch((err) => {
        console.error("Error during upload:", err);
        setIsLoading(false);
        setIsPolling(false);
        const errorMessage = err.response?.data?.error || `Ocorreu um erro: ${err.message}`;
        setError(errorMessage);
        toast.error(errorMessage);
      });
  };

  // Function to cancel ongoing transcription
  const handleCancelTranscription = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setIsPolling(false);
    setIsLoading(false);
    setJobId(null);
    toast.info("Transcrição cancelada.");
  };

  const handleDownload = () => {
    if (!transcription) return;

    let content = transcription;
    let filename = `transcrição_${fileName.split('.')[0]}.txt`;
    let contentType = "text/plain";

    // If we have JSON data and JSON format is selected
    if (formatType === "json" && transcriptionData) {
      content = JSON.stringify(transcriptionData, null, 2);
      filename = `transcrição_${fileName.split('.')[0]}.json`;
      contentType = "application/json";
    }

    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Transcrição transferida com sucesso!");
  };

  // Função para formatar timestamps corrigida
  const formatTimestamp = (seconds) => {
    if (seconds === undefined || seconds === null) return "00:00.00";

    // Converter para número, caso seja uma string
    seconds = Number(seconds);

    // Verificar se o valor está em um formato não convencional
    // Se o valor for muito grande (acima de 3600), podemos assumir que está em milissegundos
    if (seconds > 3600) {
      // Converter de milissegundos para segundos
      seconds = seconds / 1000;
    }

    // Calcular minutos e segundos
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = (seconds % 60).toFixed(2);

    // Formatar com padding (00:00.00)
    // padStart só funciona com strings, precisamos garantir que remainingSeconds seja uma string
    const formattedSeconds = remainingSeconds.toString().padStart(5, '0');
    return `${minutes.toString().padStart(2, '0')}:${formattedSeconds}`;
  };

  // Função para gerar o PDF com o diálogo formatado
  const generateCourtTranscriptPDF = () => {
    if (!transcriptionData || !transcriptionData.utterances) {
      toast.error("Não há transcrição disponível para exportar como PDF");
      return;
    }

    try {
      // Create a new PDF document
      const doc = new jsPDF();

      // Document settings
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 20;
      const contentWidth = pageWidth - 2 * margin;

      // Header with title
      doc.setFillColor(41, 65, 148);
      doc.rect(0, 0, pageWidth, 25, 'F');

      doc.setTextColor(255, 255, 255);
      doc.setFontSize(16);
      doc.setFont("helvetica", "bold");
      const title = `Transcrição: ${fileName.split('.')[0]}`;
      doc.text(title, pageWidth / 2, 16, { align: "center" });

      // Start position after header
      let yPosition = 40;

      // Add each utterance
      transcriptionData.utterances.forEach((utterance, index) => {
        // Format timestamp - always show at beginning of utterance
        let timestamp = "";
        if (utterance.start !== undefined) {
          timestamp = `[${formatTimestamp(utterance.start)}] `;
        }

        // Get custom speaker name
        const speakerName = speakerNames[utterance.speaker] || `Falante ${utterance.speaker}`;

        // Format the speaker's line
        doc.setFont("helvetica", "bold");
        doc.setTextColor(0, 0, 0);
        doc.setFontSize(11);

        // Add timestamp + speaker
        const speakerWithTimestamp = `${timestamp}${speakerName}: `;

        // Calculate width of the speaker prefix
        const speakerWidth = doc.getTextWidth(speakerWithTimestamp);

        // Check if we need a new page before starting this utterance
        if (yPosition > pageHeight - 30) {
          doc.addPage();
          yPosition = 30;
        }

        // Add the complete line (speaker + text) as one flowing paragraph
        doc.setFont("helvetica", "bold");
        doc.text(speakerWithTimestamp, margin, yPosition);

        // Add the text right after the speaker name
        doc.setFont("helvetica", "normal");

        // Format utterance text to flow naturally on the page
        const maxWidth = contentWidth - speakerWidth;
        const utteranceText = utterance.text;

        // Split text into words
        const words = utteranceText.split(' ');
        let currentLine = '';
        let currentX = margin + speakerWidth;

        // Process the first word specially to attach it to the speaker name
        if (words.length > 0) {
          currentLine = words[0];
          doc.text(currentLine, currentX, yPosition);
          currentX += doc.getTextWidth(currentLine + ' ');
        }

        // Process the rest of the words
        for (let i = 1; i < words.length; i++) {
          const word = words[i];
          const wordWidth = doc.getTextWidth(word + ' ');

          // Check if adding this word would exceed the line width
          if (currentX + wordWidth > margin + contentWidth) {
            // Move to next line
            yPosition += 6;
            currentX = margin;

            // Check if we need a new page
            if (yPosition > pageHeight - 20) {
              doc.addPage();
              yPosition = 30;
            }
          }

          // Add the word
          doc.text(word, currentX, yPosition);
          currentX += wordWidth;
        }

        // Move to the next utterance
        yPosition += 12; // Add extra space between utterances
      });

      // Add page numbers
      const pageCount = doc.internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(10);
        doc.setTextColor(100, 100, 100);
        doc.text(`Página ${i} de ${pageCount}`, pageWidth / 2, pageHeight - 10, { align: 'center' });
      }

      // Save the PDF
      doc.save(`transcrição_judicial_${fileName.split('.')[0]}.pdf`);
      toast.success("PDF da transcrição judicial gerado com sucesso!");
    } catch (error) {
      console.error("Erro ao gerar PDF:", error);
      toast.error("Erro ao gerar o PDF. Por favor, tente novamente.");
    }
  };

  const handleCopyToClipboard = () => {
    if (!transcription) return;

    navigator.clipboard.writeText(transcription)
      .then(() => toast.success("Texto copiado para a área de transferência!"))
      .catch(() => toast.error("Falha ao copiar o texto"));
  };

  const handleReset = () => {
    // Clear any ongoing polling
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setIsPolling(false);
    setJobId(null);

    setFile(null);
    setFileName("");
    setTranscription("");
    setTranscriptionData(null);
    setError("");
    setTranscriptionTime(null);
    setSpeakerNames({});
    setEditingNames(false);
    setEditableTranscription(null);
    setIsEditing(false);

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

  const handleFormatChange = (e) => {
    setFormatType(e.target.value);
  };

  // Função para iniciar a edição de nomes dos falantes
  const startEditingSpeakerNames = () => {
    setEditingNames(true);
  };

  // Função para salvar nomes dos falantes
  const saveEditingSpeakerNames = () => {
    setEditingNames(false);
    toast.success("Nomes dos falantes personalizados salvos!");
  };

  // Função para atualizar o nome de um falante específico
  const updateSpeakerName = (speaker, newName) => {
    setSpeakerNames(prev => ({
      ...prev,
      [speaker]: newName
    }));
  };

  return (
    <div className="main">
      <Header />
      <div
        className="p-6 bg-white min-h-screen"
        style={{ marginLeft: "3%" }}
      >
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
                      className={`border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-all ${dragActive
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
                        accept=".mp3,.m4a,.wav,.ogg,.flac,audio/*"
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
                            MP3, M4A, WAV, OGG, FLAC até 100 MB
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
                        className={`flex items-center justify-center py-3 px-6 rounded-lg font-medium shadow-sm transition ${isLoading || !file
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
                  <div className="mt-2 fade-in">
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

                    {/* Botão para personalizar os nomes dos falantes */}
                    {formatType === "json" && transcriptionData && transcriptionData.utterances && (
                      <div className="mb-4">
                        {!editingNames ? (
                          <button
                            onClick={startEditingSpeakerNames}
                            className="flex items-center text-blue-600 hover:text-blue-800 transition-colors"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              className="h-5 w-5 mr-1"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                              />
                            </svg>
                            Personalizar nomes dos falantes
                          </button>
                        ) : (
                          <div className="bg-blue-50 p-4 rounded-lg mb-4">
                            <h3 className="text-lg font-medium text-blue-800 mb-3">Personalizar nomes dos falantes</h3>
                            <div className="space-y-3">
                              {Object.entries(speakerNames).map(([speaker, name]) => (
                                <div key={speaker} className="flex items-center">
                                  <label className="mr-2 w-24 text-sm font-medium text-gray-700">
                                    Falante {speaker}:
                                  </label>
                                  <input
                                    type="text"
                                    value={name}
                                    onChange={(e) => updateSpeakerName(speaker, e.target.value)}
                                    className="flex-1 shadow-sm focus:ring-blue-500 focus:border-blue-500 block sm:text-sm border-gray-300 rounded-md"
                                    placeholder={`Nome do Falante ${speaker}`}
                                  />
                                </div>
                              ))}
                            </div>
                            <div className="mt-4 flex justify-end">
                              <button
                                onClick={saveEditingSpeakerNames}
                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                              >
                                Salvar nomes
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Display transcription based on format */}
                    {/* Display transcription based on format */}
                    {formatType === "json" && transcriptionData && transcriptionData.utterances ? (
                      <>
                        {isEditing ? (
                          <TranscriptEditor />
                        ) : (
                          <TranscriptionViewer />
                        )}




                      </>
                    ) : (
                      <div className="bg-gray-50 p-6 rounded-lg border border-gray-200 mb-6 max-h-96 overflow-y-auto whitespace-pre-wrap text-gray-700">
                        {transcription}
                      </div>
                    )}

                    <div className="flex flex-wrap gap-3">
                      {/* Botão para gerar PDF */}
                      {formatType === "json" && transcriptionData && transcriptionData.utterances && (
                        <button
                          onClick={generateCourtTranscriptPDF}
                          className="flex items-center bg-green-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-green-700 transition shadow-sm hover:shadow"
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
                              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                            />
                          </svg>
                          Gerar PDF
                        </button>
                      )}

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
                        Transferir Ficheiro {formatType === "json" ? "JSON" : "de Texto"}
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
                  <div className="mt-8 fade-in">
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
          </div>
        </div>
      </div>
    </div>
  );
}

export default AudioTranscription;