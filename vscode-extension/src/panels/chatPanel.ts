import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { detectIntent } from '../intentRouter';
import { ExecutionEngine, getWorkspaceRoot, isRawRipCommand } from '../executionEngine';
import { ServerManager } from '../client/serverManager';
import {
  ChatMessage,
  RipCommand,
  SessionManager,
  createMessage,
} from '../sessionManager';
import {
  composeError,
  composeResponse,
  extractSearchTargets,
} from '../responseComposer';

export class ChatPanel {
  private static currentPanel: ChatPanel | undefined;
  private readonly panel: vscode.WebviewPanel;
  private readonly session = new SessionManager();
  private readonly executionEngine: ExecutionEngine;
  private status = {
    mode: 'CLI first',
    server: 'checking',
    indexed: 'unknown',
    workspace: 'no workspace',
  };

  static createOrShow(extensionUri: vscode.Uri, serverManager: ServerManager): ChatPanel {
    if (ChatPanel.currentPanel) {
      ChatPanel.currentPanel.panel.reveal(vscode.ViewColumn.Beside);
      return ChatPanel.currentPanel;
    }

    const panel = vscode.window.createWebviewPanel('ripChat', 'RIP Chat', vscode.ViewColumn.Beside, {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.joinPath(extensionUri, 'webviews', 'chat'),
        vscode.Uri.joinPath(extensionUri, 'node_modules', 'mermaid', 'dist'),
      ],
      retainContextWhenHidden: true,
    });
    ChatPanel.currentPanel = new ChatPanel(panel, extensionUri, serverManager);
    return ChatPanel.currentPanel;
  }

  static async reveal(
    extensionUri: vscode.Uri,
    serverManager: ServerManager,
    query?: string,
    command: RipCommand = 'auto'
  ): Promise<void> {
    const panel = ChatPanel.createOrShow(extensionUri, serverManager);
    const trimmedQuery = query?.trim();
    if (trimmedQuery) {
      await panel.runQuery(trimmedQuery, command);
      return;
    }
    await panel.refreshStatus();
    await panel.postMessages();
  }

  static openWithQuery(
    extensionUri: vscode.Uri,
    serverManager: ServerManager,
    query: string,
    command: RipCommand = 'auto'
  ): void {
    void ChatPanel.reveal(extensionUri, serverManager, query, command);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    private readonly extensionUri: vscode.Uri,
    private readonly serverManager: ServerManager
  ) {
    this.panel = panel;
    this.executionEngine = new ExecutionEngine(serverManager);
    this.panel.webview.html = this.getHtml();

    this.panel.onDidDispose(() => {
      ChatPanel.currentPanel = undefined;
    });

    this.panel.webview.onDidReceiveMessage(
      (message: { type: string; query?: string; command?: RipCommand }) => {
        if (message.type === 'ready') {
          void this.refreshStatus();
          void this.postMessages();
        }
        if (message.type === 'query' && message.query) {
          void this.runQuery(message.query, message.command || 'auto');
        }
        if (message.type === 'reset') {
          this.session.reset();
          this.addWelcomeMessage();
          void this.postMessages();
        }
        if (message.type === 'refreshStatus') {
          void this.refreshStatus();
        }
      }
    );

    this.status.workspace = vscode.workspace.workspaceFolders?.[0]?.name || 'workspace';
    this.addWelcomeMessage();
    void this.refreshStatus();
  }

  private addWelcomeMessage(): void {
    if (this.session.getMessages().length > 0) {
      return;
    }
    this.addAssistantMessage([
      {
        type: 'text',
        title: 'Orchestration Agent',
        data: 'RIP is ready to inspect the repository graph, search code, trace flows, and explain impact. Ask naturally or start from one of the task cards.',
      },
      {
        type: 'suggestion',
        title: 'Suggested tasks',
        data: [
          'How does indexing work?',
          'Find parser code',
          'Trace GraphBuilder',
          'Show top risk metrics',
        ],
      },
    ]);
  }

  private async runQuery(query: string, selectedCommand: RipCommand): Promise<void> {
    const userMessage = createMessage('user', [{ type: 'text', data: query }]);
    this.session.addMessage(userMessage);
    await this.postMessages();

    let pending: ChatMessage | undefined;
    let liveTerminalOutput: string | undefined;
    try {
      const workspaceRoot = getWorkspaceRoot();
      if (isRawRipCommand(query)) {
        liveTerminalOutput = `$ ${normalizeRawCommand(query)}\n`;
        pending = createMessage('assistant', [
          {
            type: 'status',
            title: 'Running',
            data: {
              command: 'raw CLI',
              mode: 'CLI',
              workspace: workspaceRoot,
            },
          },
          {
            type: 'code',
            title: 'Terminal',
            language: 'terminal',
            data: liveTerminalOutput,
          },
        ]);
        this.session.addMessage(pending);
        await this.postMessages();

        const result = await this.executionEngine.executeRawCommand(query, workspaceRoot, async (chunk, stream) => {
          liveTerminalOutput += stream === 'stderr' ? prefixStderr(chunk) : chunk;
          updateTerminalBlock(pending, liveTerminalOutput || '');
          await this.postMessages();
        });
        const rawIntent = {
          command: result.command,
          confidence: 1,
          parameters: { query },
          reasoning: 'Executed exact RIP CLI command from chat',
        };
        const finalTerminal = [
          `$ ${result.commandLine || normalizeRawCommand(query)}`,
          result.stdout?.trimEnd() || '',
          result.stderr?.trimEnd() ? `[stderr]\n${result.stderr.trimEnd()}` : '',
        ].filter(Boolean).join('\n');
        pending.content = [
          { type: 'code', title: 'Terminal', language: 'terminal', data: finalTerminal },
          ...composeResponse(rawIntent, result, this.session.getContext()),
        ];
        pending.metadata = {
          command: result.command,
          confidence: 1,
          executionTime: result.durationMs,
          mode: result.mode,
          reasoning: result.commandLine || query,
        };
        this.status.mode = 'CLI';
        await this.refreshStatus();
        await this.postMessages();
        return;
      }

      const intent = detectIntent(query, selectedCommand, this.session.getContext());
      this.session.updateFromIntent(intent, query);
      pending = createMessage('assistant', [
        {
          type: 'status',
          title: 'Running',
          data: {
            command: intent.command,
            mode: 'CLI first',
            target: intent.target || query,
          },
        },
        {
          type: 'code',
          title: 'Terminal',
          language: 'terminal',
          data: formatTerminalRun(intent.command, String(intent.parameters.query || intent.target || query)),
        },
      ]);
      this.session.addMessage(pending);
      await this.postMessages();

      const result = await this.executionEngine.execute(intent, workspaceRoot);
      if (intent.command === 'search') {
        this.session.updateSearchResults(extractSearchTargets(result));
      }
      pending.content = composeResponse(intent, result, this.session.getContext());
      pending.metadata = {
        command: intent.command,
        confidence: intent.confidence,
        executionTime: result.durationMs,
        mode: result.mode,
        reasoning: intent.reasoning,
      };
      this.status.mode = result.mode === 'cli' ? 'CLI' : 'HTTP';
    } catch (error) {
      if (pending) {
        pending.content = liveTerminalOutput
          ? [
              { type: 'code', title: 'Terminal', language: 'terminal', data: liveTerminalOutput },
              ...composeError(error),
            ]
          : composeError(error);
      } else {
        this.session.addMessage(createMessage('assistant', composeError(error)));
      }
    }
    await this.refreshStatus();
    await this.postMessages();
  }

  private addAssistantMessage(content: ChatMessage['content']): void {
    this.session.addMessage(createMessage('assistant', content));
    void this.postMessages();
  }

  private async postMessages(): Promise<void> {
    await this.panel.webview.postMessage({
      type: 'messages',
      messages: this.session.getMessages(),
      context: this.session.getContext(),
      status: this.status,
    });
  }

  private async refreshStatus(): Promise<void> {
    const folder = vscode.workspace.workspaceFolders?.[0];
    this.status.workspace = folder?.name || 'no workspace';
    try {
      const api = this.serverManager.getApiClient();
      const status = await api.getIndexStatus();
      const data = status?.data || {};
      const count = data.entity_count ?? data.total_entities ?? 0;
      this.status.server = 'online';
      this.status.indexed = `${count} entities`;
    } catch {
      this.status.server = 'offline';
      this.status.indexed = 'CLI fallback';
    }
    await this.postMessages();
  }

  private getHtml(): string {
    const webview = this.panel.webview;
    const root = vscode.Uri.joinPath(this.extensionUri, 'webviews', 'chat');
    const htmlPath = path.join(root.fsPath, 'index.html');
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(root, 'chat.js'));
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(root, 'chat.css'));
    const mermaidUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js')
    );
    const nonce = getNonce();
    return fs
      .readFileSync(htmlPath, 'utf8')
      .replaceAll('${cspSource}', webview.cspSource)
      .replaceAll('${nonce}', nonce)
      .replaceAll('${scriptUri}', scriptUri.toString())
      .replaceAll('${mermaidUri}', mermaidUri.toString())
      .replaceAll('${styleUri}', styleUri.toString());
  }
}

function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let nonce = '';
  for (let i = 0; i < 32; i += 1) {
    nonce += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return nonce;
}

function formatTerminalRun(command: Exclude<RipCommand, 'auto'>, query: string): string {
  const quoted = query.trim() ? `"${query.trim().replace(/"/g, '\\"')}"` : '';
  const args: Record<Exclude<RipCommand, 'auto'>, string> = {
    explain: `uv run repo explain ${quoted} --diagram --tree --deps`,
    search: `uv run repo search ${quoted} --limit 12`,
    trace: `uv run repo trace ${quoted} --format json`,
    impact: `uv run repo impact ${quoted} --format json`,
    architecture: 'uv run repo architecture --format json',
    metrics: 'uv run repo metrics --top-risk 10',
  };
  return [
    `$ ${args[command]}`,
    '> resolving workspace project',
    '> checking local index',
    '> streaming RIP result',
  ].join('\n');
}

function normalizeRawCommand(query: string): string {
  return query.trim().replace(/^PS\s+[^>]+>\s*/i, '');
}

function prefixStderr(chunk: string): string {
  return chunk
    .split(/\r?\n/)
    .map((line) => (line ? `[stderr] ${line}` : line))
    .join('\n');
}

function updateTerminalBlock(message: ChatMessage | undefined, output: string): void {
  const terminal = message?.content.find(
    (block) => block.type === 'code' && block.title === 'Terminal'
  );
  if (terminal) {
    terminal.data = output;
  }
}
