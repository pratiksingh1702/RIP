import * as vscode from 'vscode';
import { ServerManager } from './client/serverManager';
import { FileSaveWatcher } from './watchers/fileSaveWatcher';
import { HoverProvider } from './providers/hoverProvider';
import { CodeActionProvider } from './providers/codeActionProvider';
import { DefinitionProvider } from './providers/definitionProvider';
import { ChatPanel } from './panels/chatPanel';
import { RipCommand } from './sessionManager';
import { RipStatusBar } from './statusBar';

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const serverManager = new ServerManager();
  const statusBar = new RipStatusBar(serverManager);
  context.subscriptions.push(serverManager, statusBar);

  const config = vscode.workspace.getConfiguration('rip');
  if (config.get<boolean>('autoStartServer', false)) {
    void serverManager.startServer();
  }

  const fileWatcher = new FileSaveWatcher(serverManager);
  context.subscriptions.push(fileWatcher);

  context.subscriptions.push(
    vscode.languages.registerHoverProvider(
      { scheme: 'file', language: '*' },
      new HoverProvider(serverManager)
    )
  );

  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      { scheme: 'file', language: '*' },
      new CodeActionProvider(serverManager)
    )
  );

  context.subscriptions.push(
    vscode.languages.registerDefinitionProvider(
      { scheme: 'file', language: '*' },
      new DefinitionProvider(serverManager)
    )
  );

  registerChatCommand('rip.openChat', undefined, 'auto');
  registerChatCommand('rip.search', 'Search this codebase', 'search');
  registerChatCommand('rip.showArchitecture', 'Show the architecture', 'architecture');
  registerChatCommand('rip.showMetrics', 'Show top risk metrics', 'metrics');
  registerSymbolCommand('rip.explain', 'explain');
  registerSymbolCommand('rip.trace', 'trace');
  registerSymbolCommand('rip.impact', 'impact');

  context.subscriptions.push(
    vscode.commands.registerCommand('rip.indexRepo', async () => {
      const folder = vscode.workspace.workspaceFolders?.[0];
      if (!folder) {
        vscode.window.showErrorMessage('Open a workspace folder before indexing with RIP.');
        return;
      }
      await ChatPanel.reveal(context.extensionUri, serverManager, 'Index this repository', 'auto');
      try {
        await serverManager.getApiClient().indexRepo(folder.uri.fsPath);
        await statusBar.refresh();
      } catch (error) {
        vscode.window.showErrorMessage(`RIP index failed: ${error}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('rip.checkStatus', async () => {
      await statusBar.refresh();
      await ChatPanel.reveal(context.extensionUri, serverManager, 'Show repository metrics', 'metrics');
    })
  );

  registerLegacyAliases(context, context.extensionUri, serverManager);

  function registerChatCommand(
    commandId: string,
    query: string | undefined,
    command: RipCommand
  ): void {
    context.subscriptions.push(
      vscode.commands.registerCommand(commandId, async () => {
        await ChatPanel.reveal(context.extensionUri, serverManager, query, command);
      })
    );
  }

  function registerSymbolCommand(commandId: string, command: RipCommand): void {
    context.subscriptions.push(
      vscode.commands.registerCommand(commandId, async (symbol?: string) => {
        const target = symbol || getSelectedSymbol();
        if (!target) {
          vscode.window.showWarningMessage('Select a symbol or place the cursor on one first.');
          return;
        }
        await ChatPanel.reveal(context.extensionUri, serverManager, `${command} ${target}`, command);
      })
    );
  }
}

function registerLegacyAliases(
  context: vscode.ExtensionContext,
  extensionUri: vscode.Uri,
  serverManager: ServerManager
): void {
  const aliases: Array<[string, string, RipCommand]> = [
    ['repoIntel.trace', 'trace', 'trace'],
    ['repoIntel.impact', 'impact', 'impact'],
    ['repoIntel.explain', 'explain', 'explain'],
    ['repoIntel.showArchitecture', 'Show the architecture', 'architecture'],
    ['repoIntel.showDependencyGraph', 'Show the architecture', 'architecture'],
  ];

  for (const [legacyId, queryOrVerb, command] of aliases) {
    context.subscriptions.push(
      vscode.commands.registerCommand(legacyId, async (symbol?: string) => {
        const query =
          command === 'architecture'
            ? queryOrVerb
            : `${queryOrVerb} ${symbol || getSelectedSymbol() || ''}`.trim();
        await ChatPanel.reveal(extensionUri, serverManager, query, command);
      })
    );
  }
}

function getSelectedSymbol(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return undefined;
  }
  const selectionText = editor.document.getText(editor.selection).trim();
  if (selectionText) {
    return selectionText;
  }
  const range = editor.document.getWordRangeAtPosition(editor.selection.start);
  return range ? editor.document.getText(range) : undefined;
}

export function deactivate(): void {
  // VS Code disposes registered subscriptions.
}
