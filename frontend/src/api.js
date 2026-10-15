const base =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${base}${path}`, { ...options, headers, credentials: "include" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : response.statusText;
    const error = new Error(message || "Request failed");
    error.status = response.status;
    throw error;
  }
  return data;
}

export function pollJob(jobId, onUpdate) {
  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    try {
      const job = await api(`/jobs/${jobId}`);
      onUpdate(job);
      if (job.status === "done" || job.status === "error") return;
    } catch (error) {
      onUpdate({ status: "error", progress: "error", error: error.message });
      return;
    }
    window.setTimeout(tick, 1000);
  };
  tick();
  return () => {
    stopped = true;
  };
}
