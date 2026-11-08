const PANEL_HOSTS = new Set([
  "masshtab-lead.ru",
  "www.masshtab-lead.ru",
  "xn----7sbaeqxud0ck9d.xn--p1ai",
  "www.xn----7sbaeqxud0ck9d.xn--p1ai",
]);

export function isMasshtabHost(hostname) {
  return PANEL_HOSTS.has(String(hostname || "").toLowerCase());
}

export function isPanelPath(pathname) {
  const path = pathname || "";
  return path === "/panel" || path.startsWith("/panel/");
}

export function isCabinetPath(pathname) {
  const path = pathname || "";
  return path === "/custom" || path.startsWith("/custom/") || isPanelPath(path);
}

export function cabinetPrefix(pathname) {
  if (typeof pathname === "string") {
    return isPanelPath(pathname) ? "/panel" : "/custom";
  }
  if (typeof window !== "undefined") {
    if (isPanelPath(window.location.pathname) || isMasshtabHost(window.location.hostname)) {
      return "/panel";
    }
  }
  return "/custom";
}

export function isMasshtabPanel() {
  return cabinetPrefix() === "/panel";
}

export function mapCabinetPath(value) {
  if (typeof value !== "string" || cabinetPrefix() !== "/panel") {
    return value;
  }
  if (value === "/custom") return "/panel";
  if (value.startsWith("/custom/")) return `/panel${value.slice("/custom".length)}`;
  return value;
}
