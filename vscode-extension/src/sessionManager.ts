export type RipCommand =
  | 'auto'
  | 'explain'
  | 'search'
  | 'trace'
  | 'impact'
  | 'architecture'
  | 'metrics';

export type ContentType =
  | 'text'
  | 'tree'
  | 'mermaid'
  | 'table'
  | 'code'
  | 'suggestion'
  | 'error'
  | 'status';

export interface IntentResult {
  command: Exclude<RipCommand, 'auto'>;
  confidence: number;
  parameters: Record<string, string | number | boolean | undefined>;
  reasoning: string;
  target?: string;
}

export interface MessageContent {
  type: ContentType;
  data: unknown;
  title?: string;
  language?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  timestamp: number;
  content: MessageContent[];
  metadata?: {
    command?: string;
    confidence?: number;
    executionTime?: number;
    mode?: string;
    reasoning?: string;
  };
}

export interface CommandResult {
  command: Exclude<RipCommand, 'auto'>;
  mode: 'cli' | 'http';
  stdout?: string;
  stderr?: string;
  data?: unknown;
  durationMs: number;
  commandLine?: string;
}

export interface ChatContext {
  lastQuery?: string;
  lastCommand?: Exclude<RipCommand, 'auto'>;
  lastTarget?: string;
  lastExplainedSymbol?: string;
  lastTracedSymbol?: string;
  lastImpactedSymbol?: string;
  lastSearchResults?: string[];
  activeFeature?: string;
}

export class SessionManager {
  private messages: ChatMessage[] = [];
  private context: ChatContext = {};

  getMessages(): ChatMessage[] {
    return this.messages;
  }

  getContext(): ChatContext {
    return this.context;
  }

  addMessage(message: ChatMessage): void {
    this.messages.push(message);
  }

  updateFromIntent(intent: IntentResult, query: string): void {
    this.context.lastQuery = query;
    this.context.lastCommand = intent.command;
    if (intent.target) {
      this.context.lastTarget = intent.target;
    }
    if (intent.command === 'explain' && intent.target) {
      this.context.lastExplainedSymbol = intent.target;
    }
    if (intent.command === 'trace' && intent.target) {
      this.context.lastTracedSymbol = intent.target;
    }
    if (intent.command === 'impact' && intent.target) {
      this.context.lastImpactedSymbol = intent.target;
    }
  }

  updateSearchResults(results: string[]): void {
    this.context.lastSearchResults = results;
    if (results.length > 0) {
      this.context.lastTarget = results[0];
    }
  }

  reset(): void {
    this.messages = [];
    this.context = {};
  }
}

export function createMessage(
  role: ChatMessage['role'],
  content: MessageContent[],
  metadata: ChatMessage['metadata'] = {}
): ChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    timestamp: Date.now(),
    content,
    metadata,
  };
}
