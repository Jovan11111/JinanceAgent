function parseMarkdown(source) {
  const lines = String(source || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const blocks = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.trim().startsWith("```")) {
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: "code", text: code.join("\n") });
      continue;
    }
    if (tableAt(lines, index)) {
      const headers = cells(lines[index]);
      index += 2;
      const rows = [];
      while (index < lines.length && isRow(lines[index])) {
        rows.push(cells(lines[index]));
        index += 1;
      }
      blocks.push({ type: "table", headers, rows });
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2].trim() });
      index += 1;
      continue;
    }
    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      const ordered = /^\d+\.\s+/.test(line);
      const items = [];
      while (index < lines.length) {
        const bullet = /^[-*]\s+(.*)$/.exec(lines[index]);
        const number = /^\d+\.\s+(.*)$/.exec(lines[index]);
        if (ordered && number) items.push(number[2].trim());
        else if (!ordered && bullet) items.push(bullet[1].trim());
        else break;
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const paragraph = [];
    while (index < lines.length && lines[index].trim() && !special(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraph.join("\n") });
  }
  return blocks;
}

function parseInline(text) {
  const pattern = /(\*\*[^*]+?\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|\*[^\s*](?:[^*]*[^\s*])?\*)/g;
  const tokens = [];
  let last = 0;
  for (const match of String(text).matchAll(pattern)) {
    if (match.index > last) tokens.push({ type: "text", text: text.slice(last, match.index) });
    const token = match[0];
    if (token.startsWith("**")) tokens.push({ type: "strong", text: token.slice(2, -2) });
    else if (token.startsWith("`")) tokens.push({ type: "code", text: token.slice(1, -1) });
    else if (token.startsWith("[")) {
      const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(token);
      const href = link ? safeUrl(link[2]) : null;
      tokens.push(href ? { type: "link", text: link[1], href } : { type: "text", text: token });
    } else tokens.push({ type: "em", text: token.slice(1, -1) });
    last = match.index + token.length;
  }
  if (last < text.length) tokens.push({ type: "text", text: text.slice(last) });
  return tokens;
}

function renderMarkdown(container, source) {
  for (const block of parseMarkdown(source)) {
    if (block.type === "code") {
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = block.text;
      pre.append(code);
      container.append(pre);
      continue;
    }
    if (block.type === "table") {
      container.append(renderTable(block));
      continue;
    }
    if (block.type === "heading") {
      const heading = document.createElement("h" + block.level);
      appendInline(heading, block.text);
      container.append(heading);
      continue;
    }
    if (block.type === "list") {
      const list = document.createElement(block.ordered ? "ol" : "ul");
      for (const item of block.items) {
        const li = document.createElement("li");
        appendInline(li, item);
        list.append(li);
      }
      container.append(list);
      continue;
    }
    const paragraph = document.createElement("p");
    const parts = block.text.split("\n");
    parts.forEach((part, partIndex) => {
      if (partIndex) paragraph.append(document.createElement("br"));
      appendInline(paragraph, part);
    });
    container.append(paragraph);
  }
}

function renderTable(block) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const header of block.headers) {
    const cell = document.createElement("th");
    appendInline(cell, header);
    head.append(cell);
  }
  const thead = document.createElement("thead");
  thead.append(head);
  const body = document.createElement("tbody");
  for (const row of block.rows) {
    const tr = document.createElement("tr");
    const width = Math.max(block.headers.length, row.length);
    for (let column = 0; column < width; column += 1) {
      const cell = document.createElement("td");
      appendInline(cell, row[column] || "");
      tr.append(cell);
    }
    body.append(tr);
  }
  table.append(thead, body);
  wrap.append(table);
  return wrap;
}

function appendInline(parent, text) {
  for (const token of parseInline(text)) {
    if (token.type === "text") {
      parent.append(document.createTextNode(token.text));
      continue;
    }
    const element = document.createElement(
      token.type === "strong" ? "strong" : token.type === "em" ? "em" : token.type === "code" ? "code" : "a"
    );
    element.textContent = token.text;
    if (token.type === "link") {
      element.href = token.href;
      element.target = "_blank";
      element.rel = "noopener";
    }
    parent.append(element);
  }
}

function special(lines, index) {
  const line = lines[index];
  return line.trim().startsWith("```")
    || tableAt(lines, index)
    || /^#{1,3}\s+/.test(line)
    || /^[-*]\s+/.test(line)
    || /^\d+\.\s+/.test(line);
}

function tableAt(lines, index) {
  return index + 1 < lines.length && isRow(lines[index]) && isDivider(lines[index + 1]);
}

function isRow(line) {
  const text = line.trim();
  return text.startsWith("|") && text.endsWith("|") && text.split("|").length > 2;
}

function isDivider(line) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
}

function cells(line) {
  let text = line.trim();
  if (text.startsWith("|")) text = text.slice(1);
  if (text.endsWith("|")) text = text.slice(0, -1);
  return text.split("|").map((cell) => cell.trim());
}

function safeUrl(url) {
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/") && !url.startsWith("//") && !url.includes("\\")) return url;
  return null;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseMarkdown, parseInline };
}
