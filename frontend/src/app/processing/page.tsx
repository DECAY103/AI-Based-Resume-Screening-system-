"use client";

import { ChangeEvent, FormEvent, useRef, useState } from "react";
import { processingApi, ProcessingResult } from "@/lib/api";

function fileSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function OutputCard({ result }: { result: ProcessingResult }) {
  return (
    <section className="output" aria-live="polite">
      <div className="output-heading">
        <div>
          <p className="eyebrow">Processing result</p>
          <h2>{result.input_type === "zip" ? "Batch complete" : "Resume complete"}</h2>
        </div>
        <div className="summary">
          <span><strong>{result.total_files}</strong> processed</span>
          <span className="good"><strong>{result.accepted_files}</strong> accepted</span>
          {result.rejected_files > 0 && <span className="bad"><strong>{result.rejected_files}</strong> flagged</span>}
        </div>
      </div>

      {result.files.map((file) => (
        <article className="file-result" key={file.filename}>
          <div className="file-result-title">
            <div>
              <h3>{file.filename}</h3>
              <p>Person 2 pipeline: validate → extract → anonymise → scan</p>
            </div>
            <span className={`status ${file.status}`}>{file.status}</span>
          </div>

          <div className="checks">
            <span className={file.validation_passed ? "pass" : "fail"}>
              {file.validation_passed ? "✓" : "×"} File validation
            </span>
            <span className={file.extracted_text ? "pass" : "muted"}>
              {file.extracted_text ? "✓" : "–"} Text extraction
            </span>
            <span className={file.anonymised_text ? "pass" : "muted"}>
              {file.anonymised_text ? "✓" : "–"} PII anonymisation
            </span>
            <span className={file.safety_passed === true ? "pass" : file.safety_passed === false ? "fail" : "muted"}>
              {file.safety_passed === true ? "✓" : file.safety_passed === false ? "×" : "–"} Safety scan
            </span>
          </div>

          {file.error && <p className="message error-message">{file.error}</p>}
          {file.safety_reason && <p className="message warning-message">{file.safety_reason}</p>}

          {file.extracted_text && (
            <div className="text-grid">
              <div>
                <h4>Extracted text</h4>
                <pre>{file.extracted_text}</pre>
              </div>
              <div>
                <h4>Anonymised text</h4>
                <pre>{file.anonymised_text}</pre>
              </div>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

export default function ProcessingPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function chooseFile(nextFile: File | null) {
    setFile(nextFile);
    setResult(null);
    setError(null);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0] ?? null);
  }

  async function processFile(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await processingApi.preview(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The file could not be processed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Resume screening · Person 2</p>
        <h1>See what the pipeline sees.</h1>
        <p>Upload one resume PDF or a ZIP of PDFs to validate it, extract its text, remove personal information, and run the safety scan.</p>
      </header>

      <form className="upload-card" onSubmit={processFile}>
        <input ref={inputRef} className="file-control" id="resume-file" type="file" accept=".pdf,.zip,application/pdf,application/zip" onChange={onFileChange} />
        <button className="file-picker" type="button" onClick={() => inputRef.current?.click()}>
          <span className="file-picker__icon">↑</span>
          <span><strong>{file ? "Choose another file" : "Select a PDF or ZIP"}</strong><small>{file ? `${file.name} · ${fileSize(file.size)}` : "PDF up to 5 MB · ZIP up to 50 MB"}</small></span>
        </button>
        <div className="upload-actions">
          <p>Nothing is ranked or saved here—this shows only the ingestion and sanitisation output.</p>
          <button className="primary" type="submit" disabled={!file || loading}>
            {loading ? "Processing…" : "Process file"}
          </button>
        </div>
        {error && <p className="message error-message" role="alert">{error}</p>}
      </form>

      {result && <OutputCard result={result} />}
    </main>
  );
}
