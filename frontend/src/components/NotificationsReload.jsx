import { useState } from "react";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import api from "../api";
import "../styles/Home.css";

const NotificationsComponent = ({ onRefreshComplete }) => {
  const [isLoading, setIsLoading] = useState(false);

  const refreshNotifications = async () => {
    setIsLoading(true);
  
    try {
      // Start the refresh task
      const response = await api.post("/api/refresh-notifications/");
      const taskId = response.data.task_id;
  
      toast.info(
        `Notification refresh started. You'll be notified when complete.`,
        {
          position: "bottom-right",
          autoClose: 3000,
          hideProgressBar: false,
          closeOnClick: true,
          pauseOnHover: true,
          draggable: true,
        }
      );
  
      // Poll for task completion
      const checkTaskStatus = async () => {
        try {
          const statusResponse = await api.get(`/api/task-status/${taskId}/`);
          console.log("Task status response:", statusResponse.data);
  
          if (statusResponse.data.status === "completed") {
            const newRecords = statusResponse.data.new_records || 0;
            console.log(`Task completed with ${newRecords} new records`);
  
            toast.success(
              `Notifications refreshed successfully! ${newRecords} new notifications added.`,
              {
                position: "bottom-right",
                autoClose: 5000,
                hideProgressBar: false,
                closeOnClick: true,
                pauseOnHover: true,
                draggable: true,
              }
            );
  
            // Call the onRefreshComplete callback to refresh data
            if (onRefreshComplete && typeof onRefreshComplete === "function") {
              onRefreshComplete();
            }
  
            return true;
          } else if (statusResponse.data.status === "failed") {
            console.log("Task failed:", statusResponse.data.error);
            toast.error(
              `Failed to refresh notifications: ${statusResponse.data.error}`,
              {
                position: "bottom-right",
                autoClose: 5000,
                hideProgressBar: false,
                closeOnClick: true,
                pauseOnHover: true,
                draggable: true,
              }
            );
            return true;
          }
          return false;
        } catch (err) {
          console.error("Error checking task status:", err);
          return false;
        }
      };
  
      // Poll every 3 seconds for up to 30 seconds
      let attempts = 0;
      const maxAttempts = 10;
      const interval = setInterval(async () => {
        const isDone = await checkTaskStatus();
        attempts++;
        if (isDone || attempts >= maxAttempts) {
          clearInterval(interval);
          if (attempts >= maxAttempts && !isDone) {
            toast.info(
              "Notification refresh is taking longer than expected. Check back later.",
              {
                position: "bottom-right",
                autoClose: 5000,
              }
            );
          }
        }
      }, 3000);
    } catch (err) {
      // Your existing error handling
      toast.error(`Error refreshing notifications: ${err.message}`, {
        position: "bottom-right",
        autoClose: 5000,
        hideProgressBar: false,
        closeOnClick: true,
        pauseOnHover: true,
        draggable: true,
      });
  
      // Log detailed debug info
      console.error("Error refreshing notifications:", {
        status: err.response?.status,
        statusText: err.response?.statusText,
        responseData: err.response?.data,
        url: err.config?.url,
      });
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="notifications-container relative">
      <button
        onClick={refreshNotifications}
        disabled={isLoading}
        className="refresh-button flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-75 pointer"
      >
        <svg
          className={`h-5 w-5 mr-2 ${isLoading ? "spinning" : "refresh-icon"}`}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          height="20"
          width="40"
        >
          <path d="M23 4v6h-6M1 20v-6h6" />
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
        </svg>
      </button>
    </div>
  );
};

export default NotificationsComponent;
