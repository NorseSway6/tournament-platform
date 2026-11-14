const MAP: Record<string, string> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i", й: "y",
  к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f",
  х: "h", ц: "ts", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
};

/** Латинский адрес из русского названия: «Летний кубок» → «letniy-kubok-x7k2». */
export function makeSlug(name: string) {
  const base = name
    .toLowerCase()
    .split("")
    .map((ch) => MAP[ch] ?? ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  const suffix = Math.random().toString(36).slice(2, 6);
  return base ? `${base}-${suffix}` : `t-${suffix}`;
}

/** Постоянный id устройства — нужен бэкенду для событий протокола. */
export function deviceId() {
  const key = "tp.device";
  try {
    let id = localStorage.getItem(key);
    if (!id) {
      id = uuid();
      localStorage.setItem(key, id);
    }
    return id;
  } catch {
    return (window as unknown as { __tpDevice?: string }).__tpDevice ??= uuid();
  }
}

export function uuid() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** «Иванов Иван Иванович» → части ФИО. */
export function splitFullName(full: string) {
  const [last = "", first = "", ...rest] = full.trim().split(/\s+/);
  return { last_name: last, first_name: first, middle_name: rest.join(" ") };
}

export function playerFullName(p: { last_name: string; first_name: string; middle_name?: string }) {
  return [p.last_name, p.first_name, p.middle_name].filter(Boolean).join(" ");
}

/** Локальная дата + время из полей формы → ISO с часовым поясом браузера. */
export function localInputToIso(date: string, time: string) {
  const d = new Date(`${date}T${time || "00:00"}`);
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  return `${date}T${time || "00:00"}:00${sign}${pad(offset / 60)}:${pad(offset % 60)}`;
}

export function todayInput() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
