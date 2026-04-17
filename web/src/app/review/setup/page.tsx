"use client";

import { useSearchParams } from "next/navigation";
import { useState, Suspense } from "react";
import { startRegistration } from "@simplewebauthn/browser";

// ---------------------------------------------------------------------------
// Inner component — reads search params (must be inside Suspense in Next 16)
// ---------------------------------------------------------------------------

function SetupContent() {
  const searchParams = useSearchParams();
  const secret = searchParams.get("secret") ?? "";

  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [credentialBase64, setCredentialBase64] = useState("");
  const [copied, setCopied] = useState(false);

  if (!secret) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <div
          className="w-full max-w-md p-8"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
        >
          <h1
            className="text-2xl font-bold mb-4"
            style={{ color: "#FF5C33", fontFamily: "'JetBrains Mono', monospace" }}
          >
            Invalid Setup Link
          </h1>
          <p className="text-sm" style={{ color: "#B8B9B6" }}>
            This URL is missing the <code style={{ color: "#FF8400" }}>?secret=</code> parameter.
            Use the full link provided during deployment setup.
          </p>
        </div>
      </div>
    );
  }

  async function handleRegister() {
    setStatus("loading");
    setErrorMsg("");

    try {
      // 1. Get registration challenge from server
      const challengeRes = await fetch("/api/auth/register/challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      });

      if (!challengeRes.ok) {
        const err = await challengeRes.json().catch(() => ({}));
        throw new Error((err as { error?: string }).error ?? "Failed to get registration challenge");
      }

      const options = await challengeRes.json();

      // 2. Invoke browser WebAuthn registration (Touch ID / Face ID / Windows Hello)
      const registrationResponse = await startRegistration({ optionsJSON: options });

      // 3. Verify registration on server
      const verifyRes = await fetch("/api/auth/register/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret, response: registrationResponse }),
      });

      if (!verifyRes.ok) {
        const err = await verifyRes.json().catch(() => ({}));
        throw new Error((err as { error?: string }).error ?? "Registration verification failed");
      }

      const result = await verifyRes.json();
      setCredentialBase64(result.credentialBase64 as string);
      setStatus("done");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.toLowerCase().includes("cancel") || msg.toLowerCase().includes("abort")) {
        setErrorMsg("Registration cancelled — try again.");
      } else {
        setErrorMsg(msg);
      }
      setStatus("error");
    }
  }

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(credentialBase64);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable — user can select manually
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1
        className="text-3xl font-bold mb-2"
        style={{ fontFamily: "'JetBrains Mono', monospace", color: "#FF8400" }}
      >
        Passkey Setup
      </h1>
      <p className="mb-6 text-sm" style={{ color: "#B8B9B6" }}>
        Register your device&apos;s built-in authenticator (Touch ID / Face ID / Windows Hello)
        as the sole admin credential for Carbon World.
      </p>

      {/* Step indicator */}
      <div
        className="mb-6 p-4"
        style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
      >
        <div className="text-xs font-bold mb-2" style={{ color: "#FF8400" }}>
          HOW THIS WORKS
        </div>
        <ol className="text-sm space-y-1" style={{ color: "#B8B9B6" }}>
          <li>1. Click &ldquo;Register Passkey&rdquo; below.</li>
          <li>2. Your device will prompt for Touch ID / Face ID / PIN.</li>
          <li>
            3. Copy the generated value into{" "}
            <code style={{ color: "#FF8400" }}>PASSKEY_CREDENTIAL</code> in Vercel env vars.
          </li>
          <li>4. Redeploy. Then delete (empty) the <code style={{ color: "#FF8400" }}>SETUP_SECRET</code> env var.</li>
        </ol>
      </div>

      {status !== "done" && (
        <button
          onClick={handleRegister}
          disabled={status === "loading"}
          className="w-full py-3 font-bold text-sm disabled:opacity-50 mb-4"
          style={{
            backgroundColor: "#FF8400",
            color: "#111111",
            fontFamily: "'JetBrains Mono', monospace",
            cursor: status === "loading" ? "wait" : "pointer",
          }}
        >
          {status === "loading" ? "Waiting for authenticator…" : "Register Passkey"}
        </button>
      )}

      {status === "error" && (
        <div
          className="p-4 mb-4"
          style={{ backgroundColor: "#24100B", border: "1px solid #FF5C33", color: "#FF5C33" }}
        >
          {errorMsg}
          <button
            onClick={() => setStatus("idle")}
            className="mt-2 block text-xs hover:opacity-80"
            style={{ color: "#FF8400" }}
          >
            Try again
          </button>
        </div>
      )}

      {status === "done" && credentialBase64 && (
        <div>
          <div
            className="p-4 mb-4"
            style={{ backgroundColor: "#222924", border: "1px solid #B6FFCE" }}
          >
            <div className="text-sm font-bold mb-1" style={{ color: "#B6FFCE" }}>
              ✓ Passkey registered successfully!
            </div>
          </div>

          <div
            className="p-4 mb-4"
            style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
          >
            <div className="text-xs font-bold mb-2" style={{ color: "#FF8400" }}>
              NEXT STEPS
            </div>
            <ol className="text-sm space-y-1 mb-4" style={{ color: "#B8B9B6" }}>
              <li>
                1. Copy the value below into{" "}
                <code style={{ color: "#FF8400" }}>PASSKEY_CREDENTIAL</code> in Vercel (Settings → Environment Variables).
              </li>
              <li>2. Redeploy the project.</li>
              <li>
                3. Delete (or empty) the{" "}
                <code style={{ color: "#FF8400" }}>SETUP_SECRET</code> env var to disable this setup page.
              </li>
            </ol>

            <div className="text-xs font-bold mb-2" style={{ color: "#B8B9B6" }}>
              PASSKEY_CREDENTIAL value:
            </div>
            <pre
              className="p-3 text-xs overflow-x-auto break-all whitespace-pre-wrap mb-3"
              style={{
                backgroundColor: "#111111",
                border: "1px solid #2E2E2E",
                color: "#FFFFFF",
                fontFamily: "'JetBrains Mono', monospace",
                userSelect: "all",
              }}
            >
              {credentialBase64}
            </pre>

            <button
              onClick={copyToClipboard}
              className="py-2 px-4 text-xs font-bold"
              style={{
                backgroundColor: copied ? "#222924" : "#FF8400",
                color: copied ? "#B6FFCE" : "#111111",
              }}
            >
              {copied ? "✓ Copied!" : "Copy to clipboard"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page wrapper (required Suspense for useSearchParams in Next.js App Router)
// ---------------------------------------------------------------------------

export default function SetupPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex items-center justify-center">
          <p style={{ color: "#B8B9B6" }}>Loading…</p>
        </div>
      }
    >
      <SetupContent />
    </Suspense>
  );
}
