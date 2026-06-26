"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api";
import { Upload, CheckCircle, AlertCircle } from "lucide-react";

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [accountId, setAccountId] = useState("");
  const [bankCode, setBankCode] = useState("HDFC");
  const [jobId, setJobId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => {
      const response = await apiClient.get("/api/accounts");
      return response.data;
    },
  });

  const { data: jobStatus } = useQuery({
    queryKey: ["job", jobId],
    queryFn: async () => {
      if (!jobId) return null;
      const response = await apiClient.get(`/api/jobs/${jobId}`);
      return response.data;
    },
    enabled: !!jobId,
    refetchInterval: jobId ? 2000 : false,
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError("");
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !accountId) {
      setError("Please select a file and account");
      return;
    }

    setUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("account_id", accountId);
    formData.append("bank_code", bankCode);

    try {
      const response = await apiClient.post("/api/upload-statement", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      setJobId(response.data.job_id);
      setSelectedFile(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-4xl font-bold text-gray-900 mb-8">Upload Bank Statement</h1>

      {!jobId ? (
        <form onSubmit={handleUpload} className="bg-white rounded-lg shadow p-8">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
              {error}
            </div>
          )}

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Account
            </label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Choose an account...</option>
              {accounts?.map((acc: any) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name} ({acc.type})
                </option>
              ))}
            </select>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Bank
            </label>
            <select
              value={bankCode}
              onChange={(e) => setBankCode(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="HDFC">HDFC Bank</option>
              <option value="ICICI">ICICI Bank</option>
              <option value="SBI">SBI</option>
              <option value="AXIS">Axis Bank</option>
              <option value="KOTAK">Kotak Bank</option>
              <option value="IDFC">IDFC Bank</option>
            </select>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-4">
              Select File (PDF, CSV, or Excel)
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition cursor-pointer">
              <input
                type="file"
                onChange={handleFileChange}
                accept=".pdf,.csv,.xlsx"
                className="hidden"
                id="file-input"
              />
              <label htmlFor="file-input" className="cursor-pointer">
                <Upload className="mx-auto w-12 h-12 text-gray-400 mb-2" />
                {selectedFile ? (
                  <>
                    <p className="font-medium text-gray-900">{selectedFile.name}</p>
                    <p className="text-sm text-gray-500">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-medium text-gray-900">Click to select file</p>
                    <p className="text-sm text-gray-500">or drag and drop</p>
                  </>
                )}
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={uploading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-lg transition"
          >
            {uploading ? "Uploading..." : "Upload Statement"}
          </button>
        </form>
      ) : (
        <div className="bg-white rounded-lg shadow p-8">
          <div className="text-center">
            {jobStatus?.status === "done" && (
              <>
                <CheckCircle className="mx-auto w-16 h-16 text-green-500 mb-4" />
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Complete!</h2>
                <p className="text-gray-600 mb-6">Your transactions have been imported successfully.</p>
              </>
            )}
            {jobStatus?.status === "processing" && (
              <>
                <div className="mx-auto w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Processing...</h2>
                <p className="text-gray-600">Parsing and categorizing your transactions...</p>
              </>
            )}
            {jobStatus?.status === "failed" && (
              <>
                <AlertCircle className="mx-auto w-16 h-16 text-red-500 mb-4" />
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Failed</h2>
                <p className="text-gray-600 mb-2">{jobStatus?.error || "Unknown error"}</p>
              </>
            )}
            <div className="mt-8">
              <button
                onClick={() => {
                  setJobId("");
                  setSelectedFile(null);
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
              >
                Upload Another File
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
