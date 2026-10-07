// CSV helpers shared by ingestion (JSON -> CSV) and the mock backend (CSV parsing).

export function escapeCsvValue(value) {
  if (value === null || value === undefined) return '';
  let text;
  if (value instanceof Date) text = value.toISOString();
  else if (typeof value === 'object') text = JSON.stringify(value);
  else text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows, columns) {
  const lines = [columns.map(escapeCsvValue).join(',')];
  for (const row of rows) lines.push(columns.map((column) => escapeCsvValue(row[column])).join(','));
  return `${lines.join('\r\n')}\r\n`;
}

// Delta column names can't contain spaces or ,;{}()=\n\t. Normalize keys that come from JSON.
export function safeColumnName(name) {
  const cleaned = String(name)
    .trim()
    .replace(/[^A-Za-z0-9_]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
  return cleaned || 'column';
}

function flatten(value, prefix, out, depth) {
  if (value !== null && typeof value === 'object' && !Array.isArray(value) && !(value instanceof Date) && depth < 3) {
    for (const [key, child] of Object.entries(value)) flatten(child, prefix ? `${prefix}_${key}` : key, out, depth + 1);
  } else {
    out[prefix || 'value'] = value;
  }
  return out;
}

export function extractRecords(data) {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object') {
    for (const key of ['value', 'data', 'items', 'records', 'results', 'rows']) {
      if (Array.isArray(data[key])) return data[key];
    }
    return [data];
  }
  throw new Error('The JSON has no records to load.');
}

export function jsonToCsv(data, { maxColumns = 500 } = {}) {
  const records = extractRecords(data).map((record) => (record !== null && typeof record === 'object' ? flatten(record, '', {}, 0) : { value: record }));
  if (records.length === 0) throw new Error('The JSON has no records to load.');
  const columns = [];
  const seen = new Map();
  const renamed = records.map((record) => {
    const row = {};
    for (const [key, value] of Object.entries(record)) {
      if (!seen.has(key)) {
        if (columns.length >= maxColumns) continue;
        let name = safeColumnName(key);
        while (columns.includes(name)) name = `${name}_1`;
        seen.set(key, name);
        columns.push(name);
      }
      row[seen.get(key)] = value;
    }
    return row;
  });
  return { csv: toCsv(renamed, columns), rows: renamed.length, columns };
}

// RFC 4180 parser: quoted fields, escaped quotes, CRLF or LF line endings.
export function parseCsv(text, delimiter = ',') {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  const source = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (inQuotes) {
      if (char === '"') {
        if (source[i + 1] === '"') {
          field += '"';
          i++;
        } else inQuotes = false;
      } else field += char;
    } else if (char === '"') inQuotes = true;
    else if (char === delimiter) {
      row.push(field);
      field = '';
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && source[i + 1] === '\n') i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else field += char;
  }
  if (field !== '' || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => !(r.length === 1 && r[0] === ''));
}
