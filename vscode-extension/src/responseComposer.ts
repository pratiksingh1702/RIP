import {
  ChatContext,
  CommandResult,
  IntentResult,
  MessageContent,
} from './sessionManager';

interface ApiEnvelope {
  success?: boolean;
  data?: unknown;
  error?: string | null;
  duration_ms?: number;
}

export function composeResponse(
  intent: IntentResult,
  result: CommandResult,
  context: ChatContext
): MessageContent[] {
  const data = unwrapEnvelope(result.data);
  const text = result.stdout?.trim() || stringify(data);
  const content: MessageContent[] = [];

  switch (intent.command) {
    case 'explain':
      content.push(...composeExplain(data, text));
      break;
    case 'search':
      content.push(...composeSearch(data, text));
      break;
    case 'trace':
      content.push(...composeTrace(data, text));
      break;
    case 'impact':
      content.push(...composeImpact(data, text));
      break;
    case 'architecture':
      content.push(...composeArchitecture(data, text));
      break;
    case 'metrics':
      content.push(...composeMetrics(data, text));
      break;
  }

  content.push({
    type: 'suggestion',
    title: 'Follow-up',
    data: buildSuggestions(intent, context),
  });

  if (result.stderr?.trim()) {
    content.push({
      type: 'text',
      title: 'Notes',
      data: result.stderr.trim(),
    });
  }

  return content;
}

export function composeError(error: unknown): MessageContent[] {
  return [
    {
      type: 'error',
      title: 'RIP command failed',
      data: error instanceof Error ? error.message : String(error),
    },
  ];
}

export function extractSearchTargets(result: CommandResult): string[] {
  const data = unwrapEnvelope(result.data);
  if (Array.isArray(data)) {
    return data
      .map((item) => readString(item, ['entity_id', 'fqn', 'name']))
      .filter((value): value is string => Boolean(value));
  }
  if (isRecord(data) && Array.isArray(data.results)) {
    return data.results
      .map((item) => readString(item, ['entity_id', 'fqn', 'name']))
      .filter((value): value is string => Boolean(value));
  }
  const stdout = result.stdout || '';
  return [...stdout.matchAll(/^│\s*([^│\n]+?)\s*│/gm)]
    .map((match) => match[1].trim())
    .filter((value) => value && !value.includes('FQN'));
}

function composeExplain(data: unknown, text: string): MessageContent[] {
  const content: MessageContent[] = [];
  const mermaid = extractMermaid(text) || readString(data, ['mermaid']);
  const explanation = readString(data, ['explanation']) || text;
  const tree = extractTree(text);
  content.push({ type: 'text', title: 'Overview', data: explanation });
  if (tree) {
    content.push({ type: 'tree', title: 'Workflow Tree', data: tree });
  }
  if (mermaid) {
    content.push({ type: 'mermaid', title: 'Mermaid Diagram', data: mermaid });
  }
  const table = extractBoxTable(text);
  if (table.length > 0) {
    content.push({ type: 'table', title: 'Dependencies (CALLS)', data: table });
  }
  return content;
}

function composeSearch(data: unknown, text: string): MessageContent[] {
  if (Array.isArray(data)) {
    return [{ type: 'table', title: 'Search Results', data: data }];
  }
  return [{ type: 'text', title: 'Search Results', data: text || 'No search results returned.' }];
}

function composeTrace(data: unknown, text: string): MessageContent[] {
  const content: MessageContent[] = [];
  const mermaid = readString(data, ['mermaid']) || extractMermaid(text);
  const hops = isRecord(data) && Array.isArray(data.hops) ? data.hops : undefined;
  if (mermaid) {
    content.push({ type: 'mermaid', title: 'Call Graph', data: mermaid });
  }
  if (hops) {
    content.push({ type: 'table', title: 'Trace Hops', data: hops });
  }
  content.push({ type: 'code', title: 'Raw Trace', language: 'json', data: stringify(data || text) });
  return content;
}

function composeImpact(data: unknown, text: string): MessageContent[] {
  if (isRecord(data)) {
    const rows = [
      ...(Array.isArray(data.affected_files) ? data.affected_files.map((file) => ({ type: 'file', value: file })) : []),
      ...(Array.isArray(data.affected_apis) ? data.affected_apis.map((api) => ({ type: 'api', value: api })) : []),
    ];
    return [
      {
        type: 'text',
        title: 'Impact Summary',
        data: `Risk: ${String(data.risk_level || 'unknown')}\nAffected files: ${rows.filter((r) => r.type === 'file').length}\nAffected APIs: ${rows.filter((r) => r.type === 'api').length}`,
      },
      { type: 'table', title: 'Affected Items', data: rows },
    ];
  }
  return [{ type: 'text', title: 'Impact Analysis', data: text }];
}

function composeArchitecture(data: unknown, text: string): MessageContent[] {
  const mermaid = readString(data, ['mermaid']) || extractMermaid(text);
  const services = isRecord(data) && Array.isArray(data.services) ? data.services : [];
  const dependencies = isRecord(data) && Array.isArray(data.dependencies) ? data.dependencies : [];
  return [
    ...(mermaid ? [{ type: 'mermaid' as const, title: 'Architecture', data: mermaid }] : []),
    ...(services.length ? [{ type: 'table' as const, title: 'Services', data: services }] : []),
    ...(dependencies.length ? [{ type: 'table' as const, title: 'Dependencies', data: dependencies }] : []),
    ...(!mermaid && !services.length ? [{ type: 'text' as const, title: 'Architecture', data: text }] : []),
  ];
}

function composeMetrics(data: unknown, text: string): MessageContent[] {
  if (isRecord(data) && isRecord(data.data) && Array.isArray(data.data.modules)) {
    return [{ type: 'table', title: 'Metrics', data: data.data.modules }];
  }
  if (isRecord(data) && Array.isArray(data.modules)) {
    return [{ type: 'table', title: 'Metrics', data: data.modules }];
  }
  return [{ type: 'text', title: 'Metrics', data: text }];
}

function buildSuggestions(intent: IntentResult, context: ChatContext): string[] {
  const target = intent.target || context.lastTarget || 'this symbol';
  switch (intent.command) {
    case 'explain':
      return [`What depends on ${target}?`, `Trace ${target}`, `Find related code for ${target}`];
    case 'search':
      return ['Explain the top result', 'Show architecture', 'What files are risky?'];
    case 'trace':
      return [`What depends on ${target}?`, `Explain ${target}`, 'Show architecture'];
    case 'impact':
      return [`Trace ${target}`, `Explain ${target}`, 'Show top risk metrics'];
    default:
      return ['Explain the indexing pipeline', 'Find parser code', 'Show top risk metrics'];
  }
}

function unwrapEnvelope(data: unknown): unknown {
  if (isRecord(data) && ('success' in data || 'duration_ms' in data)) {
    const envelope = data as ApiEnvelope;
    return envelope.data ?? envelope.error ?? data;
  }
  return data;
}

function extractMermaid(text: string): string | undefined {
  const fenced = text.match(/```mermaid\s*([\s\S]*?)```/i);
  if (fenced?.[1]) {
    return fenced[1].trim();
  }
  const graph = text.match(/(?:^|\n)(graph\s+(?:TD|LR|BT|RL)[\s\S]*)/i);
  return graph?.[1]?.trim();
}

function extractTree(text: string): string | undefined {
  const marker = text.match(/Workflow Tree:([\s\S]*?)(?:Mermaid Diagram:|Dependency Graph:|Analysis Summary|$)/i);
  return marker?.[1]?.trim();
}

function extractBoxTable(text: string): Array<Record<string, string>> {
  const rows = text
    .split(/\r?\n/)
    .filter((line) => line.includes('│'))
    .map((line) =>
      line
        .split('│')
        .map((cell) => cell.trim())
        .filter(Boolean)
    )
    .filter((cells) => cells.length >= 2);

  if (rows.length < 2) {
    return [];
  }
  const headers = rows[0];
  return rows.slice(1).map((cells) =>
    Object.fromEntries(headers.map((header, index) => [header, cells[index] || '']))
  );
}

function readString(data: unknown, keys: string[]): string | undefined {
  if (!isRecord(data)) {
    return undefined;
  }
  for (const key of keys) {
    const value = data[key];
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function stringify(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value, null, 2);
}
