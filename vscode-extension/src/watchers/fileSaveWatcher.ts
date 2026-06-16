import * as vscode from 'vscode';
import { ServerManager } from '../client/serverManager';

export class FileSaveWatcher {
  private disposable: vscode.Disposable;
  private debounceTimer: NodeJS.Timeout | null = null;
  private serverManager: ServerManager;

  constructor(serverManager: ServerManager) {
    this.serverManager = serverManager;
    this.disposable = vscode.workspace.onDidSaveTextDocument((document) => {
      this.handleSave(document);
    });
  }

  private handleSave(document: vscode.TextDocument): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      void this.triggerIncrementalIndex(document);
    }, 1000);
  }

  private async triggerIncrementalIndex(document: vscode.TextDocument): Promise<void> {
    try {
      const apiClient = this.serverManager.getApiClient();
      const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
      if (workspaceFolder) {
        await apiClient.indexRepo(workspaceFolder.uri.fsPath);
      }
    } catch (err) {
      console.error('Failed to trigger incremental index on save:', err);
    }
  }

  dispose(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    this.disposable.dispose();
  }
}
