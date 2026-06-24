import { ChatContext, IntentResult, RipCommand } from './sessionManager';

const commandPatterns: Array<{
  command: IntentResult['command'];
  confidence: number;
  reasoning: string;
  patterns: RegExp[];
}> = [
  {
    command: 'impact',
    confidence: 0.92,
    reasoning: 'Auto-detected impact/dependency analysis',
    patterns: [
      /\bimpact\b/i,
      /\bdepend(s|encies|ents)?\b/i,
      /what (breaks|uses|depends on|is affected)/i,
      /\baffect(ed|s)?\b/i,
    ],
  },
  {
    command: 'trace',
    confidence: 0.88,
    reasoning: 'Auto-detected trace/call-flow analysis',
    patterns: [/\btrace\b/i, /call chain/i, /\bflow\b/i, /path from/i, /execution path/i],
  },
  {
    command: 'search',
    confidence: 0.86,
    reasoning: 'Auto-detected semantic code search',
    patterns: [/\bfind\b/i, /\bsearch\b/i, /where is/i, /\blocate\b/i, /look for/i, /show me the files/i],
  },
  {
    command: 'architecture',
    confidence: 0.9,
    reasoning: 'Auto-detected architecture overview',
    patterns: [/\barchitecture\b/i, /\bstructure\b/i, /\bmodules?\b/i, /\bdesign\b/i],
  },
  {
    command: 'metrics',
    confidence: 0.88,
    reasoning: 'Auto-detected repository metrics',
    patterns: [/\bmetrics?\b/i, /\bcoupling\b/i, /\brisk\b/i, /\bhealth\b/i, /\bchurn\b/i],
  },
  {
    command: 'explain',
    confidence: 0.82,
    reasoning: 'Auto-detected explanation request',
    patterns: [/how .* work/i, /\bexplain\b/i, /what is/i, /tell me about/i, /\boverview\b/i],
  },
];

const explicitCommands = new Set<RipCommand>([
  'explain',
  'search',
  'trace',
  'impact',
  'architecture',
  'metrics',
]);

export function detectIntent(
  query: string,
  selectedCommand: RipCommand = 'auto',
  context: ChatContext = {}
): IntentResult {
  const resolvedQuery = resolveFollowUp(query, context);
  const target = extractTarget(resolvedQuery, context);

  if (selectedCommand !== 'auto' && explicitCommands.has(selectedCommand)) {
    return {
      command: selectedCommand,
      confidence: 1,
      parameters: { query: resolvedQuery },
      reasoning: `Manual command override: ${selectedCommand}`,
      target,
    };
  }

  for (const candidate of commandPatterns) {
    if (candidate.patterns.some((pattern) => pattern.test(query))) {
      return {
        command: candidate.command,
        confidence: candidate.confidence,
        parameters: { query: resolvedQuery },
        reasoning: candidate.reasoning,
        target,
      };
    }
  }

  return {
    command: 'explain',
    confidence: 0.65,
    parameters: { query: resolvedQuery },
    reasoning: 'Defaulted to explanation because no stronger intent matched',
    target,
  };
}

function resolveFollowUp(query: string, context: ChatContext): string {
  const target = context.lastTarget || context.lastExplainedSymbol || context.lastTracedSymbol;
  if (!target) {
    return query;
  }
  return query.replace(/\b(it|that|this|them|those)\b/gi, target);
}

function extractTarget(query: string, context: ChatContext): string | undefined {
  const quoted = query.match(/["'`](.+?)["'`]/);
  if (quoted?.[1]) {
    return quoted[1].trim();
  }

  const afterKeywords = query.match(
    /(?:explain|trace|impact|find|search|locate|depends on|about|for)\s+(.+)$/i
  );
  if (afterKeywords?.[1]) {
    return cleanupTarget(afterKeywords[1]);
  }

  const codeSymbol = query.match(/\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b/);
  if (codeSymbol?.[0]) {
    return codeSymbol[0];
  }

  const pascalSymbol = query.match(/\b[A-Z][A-Za-z0-9_]{2,}\b/);
  if (pascalSymbol?.[0]) {
    return pascalSymbol[0];
  }

  return context.lastTarget;
}

function cleanupTarget(target: string): string {
  return target
    .replace(/[?.!,;:]$/g, '')
    .replace(/^(the|a|an)\s+/i, '')
    .trim();
}
