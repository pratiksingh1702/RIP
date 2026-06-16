import * as vscode from 'vscode';
import * as path from 'path';
import { ServerManager } from '../client/serverManager';

export class DependencyGraphPanel {
  public static currentPanel: DependencyGraphPanel | undefined;
  public static readonly viewType = 'repoIntel.dependencyGraph';
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

    if (DependencyGraphPanel.currentPanel) {
      DependencyGraphPanel.currentPanel.panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      DependencyGraphPanel.viewType,
      'RIP Dependency Graph',
      column || vscode.ViewColumn.One,
      getWebviewOptions(extensionUri)
    );

    DependencyGraphPanel.currentPanel = new DependencyGraphPanel(
      panel,
      extensionUri,
      serverManager
    );
  }

  public static revive(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    serverManager: ServerManager
  ): void {
    DependencyGraphPanel.currentPanel = new DependencyGraphPanel(
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
    this.panel.onDidChangeViewState(
      (e) => {
        if (this.panel.visible) {
          this.update();
        }
      },
      null,
      this.disposables
    );
  }

  public dispose(): void {
    DependencyGraphPanel.currentPanel = undefined;
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
      console.error('Failed to update dependency graph:', err);
    }
  }

  private getHtmlForWebview(extensionUri: vscode.Uri): string {
    const webview = this.panel.webview;
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(extensionUri, 'webviews', 'graph', 'graph.js')
    );
    const cssUri = webview.asWebviewUri(
      vscode.Uri.joinPath(extensionUri, 'webviews', 'graph', 'graph.css')
    );

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RIP Dependency Graph</title>
  <link rel="stylesheet" href="${cssUri}">
</head>
<body>
  <div id="graph"></div>
  <script src="${scriptUri}"></script>
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
