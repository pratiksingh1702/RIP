import * as vscode from 'vscode';
import { ServerManager } from './client/serverManager';
import { FileSaveWatcher } from './watchers/fileSaveWatcher';
import { HoverProvider } from './providers/hoverProvider';
import { CodeActionProvider } from './providers/codeActionProvider';
import { DefinitionProvider } from './providers/definitionProvider';
import { DependencyGraphPanel } from './panels/dependencyGraphPanel';
import { TracePanel } from './panels/tracePanel';
import { ImpactPanel } from './panels/impactPanel';
import { ArchitecturePanel } from './panels/architecturePanel';

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const serverManager = new ServerManager();
  context.subscriptions.push(serverManager);

  await serverManager.startServer();

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

  context.subscriptions.push(
    vscode.commands.registerCommand('repoIntel.trace', async (symbol?: string) => {
      if (!symbol) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          symbol = editor.document.getText(
            editor.document.getWordRangeAtPosition(editor.selection.start)
          );
        }
      }
      if (symbol) {
        TracePanel.createOrShow(context.extensionUri, serverManager, symbol);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('repoIntel.impact', async (symbol?: string) => {
      if (!symbol) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          symbol = editor.document.getText(
            editor.document.getWordRangeAtPosition(editor.selection.start)
          );
        }
      }
      if (symbol) {
        ImpactPanel.createOrShow(context.extensionUri, serverManager, symbol);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('repoIntel.explain', async (symbol?: string) => {
      if (!symbol) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          symbol = editor.document.getText(
            editor.document.getWordRangeAtPosition(editor.selection.start)
          );
        }
      }
      if (symbol) {
        vscode.window.showInformationMessage(`Explaining ${symbol}...`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('repoIntel.showArchitecture', () => {
      ArchitecturePanel.createOrShow(context.extensionUri, serverManager);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('repoIntel.showDependencyGraph', () => {
      DependencyGraphPanel.createOrShow(context.extensionUri, serverManager);
    })
  );
}

export function deactivate(): void {
  // nothing to do
}
