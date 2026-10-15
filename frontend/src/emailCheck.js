export function emailProblem(raw) {
  const email = (raw || "").trim().toLowerCase();
  if (!email || (email.match(/@/g) || []).length !== 1) return "Enter a valid email.";
  const [local, domain] = email.split("@");
  if (!/^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?$/.test(local) || local.includes("..")) {
    return "Enter a valid email.";
  }
  const labels = domain.split(".");
  if (labels.length < 2 || domain.includes("..")) return "Enter a valid email.";
  const label = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
  if (!labels.slice(0, -1).every((part) => label.test(part))) return "Enter a valid email.";
  if (!/^[a-z]{2,24}$/.test(labels[labels.length - 1])) return "Enter a valid email.";
  return "";
}
