"use client";

import { useState, useRef, useCallback } from "react";
import { useI18n } from "@/i18n";
import { uploadResume } from "@/lib/api";
import { MAX_RESUME_SIZE_BYTES } from "@/lib/constants";
import type { ResumeUploadResponse } from "@/types";
import { cn } from "@/lib/utils";
import { Upload, FileText, X, Loader2, AlertCircle, CheckCircle } from "lucide-react";

type UploadStatus = "idle" | "dragging" | "uploading" | "parsing" | "done" | "error";

interface Props {
  onParsed: (data: ResumeUploadResponse) => void;
  onClear: () => void;
  parsed: ResumeUploadResponse | null;
}

export function ResumeUploader({ onParsed, onClear, parsed }: Props) {
  const { t } = useI18n();
  const [status, setStatus] = useState<UploadStatus>(parsed ? "done" : "idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>(parsed?.filename || "");
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): string | null => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return "Only PDF files are accepted";
    }
    if (file.size > MAX_RESUME_SIZE_BYTES) {
      return "File exceeds maximum size of 5MB";
    }
    if (file.size === 0) {
      return "File is empty";
    }
    return null;
  }, []);

  const processFile = useCallback(
    async (file: File) => {
      const error = validateFile(file);
      if (error) {
        setStatus("error");
        setErrorMsg(error);
        return;
      }

      setFileName(file.name);
      setStatus("uploading");
      setErrorMsg(null);

      try {
        const result = await uploadResume(file);

        if (result.parse_status === "failed") {
          setStatus("error");
          setErrorMsg("Failed to parse resume. The PDF may be image-based or unreadable.");
          return;
        }

        setStatus("done");
        onParsed(result);
      } catch (e) {
        setStatus("error");
        setErrorMsg(e instanceof Error ? e.message : "Upload failed");
      }
    },
    [validateFile, onParsed]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setStatus("idle");
      const file = e.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setStatus("dragging");
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setStatus((s) => (s === "dragging" ? "idle" : s));
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  const handleClear = useCallback(() => {
    setStatus("idle");
    setErrorMsg(null);
    setFileName("");
    onClear();
    if (inputRef.current) inputRef.current.value = "";
  }, [onClear]);

  const isLoading = status === "uploading" || status === "parsing";

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        📄 Upload Resume (Optional)
      </label>

      {status === "done" && parsed ? (
        /* Done state — show file info + clear button */
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-green-800 truncate">{fileName}</p>
            <p className="text-xs text-green-600">
              {parsed.parsed_data?.name || "Parsed"} · {Math.round(parsed.file_size_bytes / 1024)}KB
            </p>
          </div>
          <button
            onClick={handleClear}
            className="rounded p-1 text-green-600 hover:bg-green-100"
            aria-label="Remove file"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        /* Upload area */
        <div
          className={cn(
            "relative rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer",
            status === "dragging" && "border-blue-400 bg-blue-50",
            status === "error" && "border-red-300 bg-red-50",
            status === "idle" && "border-gray-300 hover:border-gray-400 bg-white",
            isLoading && "border-gray-300 bg-gray-50 cursor-wait"
          )}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => !isLoading && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            className="hidden"
            disabled={isLoading}
          />

          {isLoading ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              <p className="text-sm text-gray-500">
                {status === "uploading" ? "Uploading & parsing..." : "Processing..."}
              </p>
              {fileName && (
                <p className="text-xs text-gray-400 truncate max-w-full">{fileName}</p>
              )}
            </div>
          ) : status === "error" ? (
            <div className="flex flex-col items-center gap-2">
              <AlertCircle className="h-8 w-8 text-red-400" />
              <p className="text-sm text-red-600">{errorMsg}</p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleClear();
                }}
                className="text-xs text-blue-600 hover:underline"
              >
                Try again
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 pointer-events-none">
              {status === "dragging" ? (
                <>
                  <Upload className="h-8 w-8 text-blue-500" />
                  <p className="text-sm text-blue-600 font-medium">Drop your resume here</p>
                </>
              ) : (
                <>
                  <FileText className="h-8 w-8 text-gray-400" />
                  <p className="text-sm text-gray-600">
                    Drag & drop your resume PDF here, or click to browse
                  </p>
                  <p className="text-xs text-gray-400">PDF format, max 5MB</p>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
