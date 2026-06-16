import * as vscode from 'vscode';
import * as path from 'path';
import { ServerManager } from '../client/serverManager';

export class ArchitecturePanel {
  public static currentPanel: ArchitecturePanel | undefined;
  public static readonly viewType = 'repoIntel.architecture';
  private readonly panel: vscode.WebviewPanel;
  private disposables: vscode.Disposable[] = [];
  private serverManager: ServerManager;

  public static createOrShow(
    extensionUri: vscode.Uri,
    serverManager: ServerManager
  ): void {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (ArchitecturePanel.currentPanel) {
      ArchitecturePanel.currentPanel.panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ArchitecturePanel.viewType,
      'RIP Architecture',
      column || vscode.ViewColumn.One,
      getWebviewOptions(extensionUri)
    );

    ArchitecturePanel.currentPanel = new ArchitecturePanel(
      panel,
      extensionUri,
      serverManager
    );
  }

  private constructor(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    serverManager: ServerManager
  ) {
    this.panel = panel;
    this.serverManager = serverManager;

    this.panel.webview.html = this.getHtmlForWebview(extensionUri);

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
    this.update();
  }

  public dispose(): void {
    ArchitecturePanel.currentPanel = undefined;
    this.panel.dispose();
    while (this.disposables.length) {
      const x = this.disposables.pop();
      if (x) {
        x.dispose();
      }
    }
  }

  private async update(): Promise<void> {
    try {
      const apiClient = this.serverManager.getApiClient();
      const architecture = await apiClient.getArchitecture();
      if (architecture && architecture.success) {
        this.panel.webview.postMessage({
          type: 'update',
          data: architecture.data,
        });
      }
    } catch (err) {
      console.error('Failed to update architecture view:', err);
    }
  }

  private getHtmlForWebview(extensionUri: vscode.Uri): string {
    const webview = this.panel.webview;
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RIP Architecture</title>
</head>
<body>
  <div id="content"></div>
</body>
</html>`;
  }
}

function getWebviewOptions(extensionUri: vscode.Uri): vscode.WebviewOptions {
  return {
    enableScripts: true,
    localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'webviews')],
  };
}
