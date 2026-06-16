import * as vscode from 'vscode';
import * as path from 'path';
import { ServerManager } from '../client/serverManager';

export class TracePanel {
  public static currentPanel: TracePanel | undefined;
  public static readonly viewType = 'repoIntel.trace';
  private readonly panel: vscode.WebviewPanel;
  private disposables: vscode.Disposable[] = [];
  private serverManager: ServerManager;
  private symbol: string;

  public static createOrShow(
    extensionUri: vscode.Uri,
    serverManager: ServerManager,
    symbol: string
  ): void {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (TracePanel.currentPanel) {
      TracePanel.currentPanel.symbol = symbol;
      TracePanel.currentPanel.update();
      TracePanel.currentPanel.panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      TracePanel.viewType,
      `RIP Trace: ${symbol}`,
      column || vscode.ViewColumn.One,
      getWebviewOptions(extensionUri)
    );

    TracePanel.currentPanel = new TracePanel(
      panel,
      extensionUri,
      serverManager,
      symbol
    );
  }

  private constructor(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    serverManager: ServerManager,
    symbol: string
  ) {
    this.panel = panel;
    this.serverManager = serverManager;
    this.symbol = symbol;

    this.panel.webview.html = this.getHtmlForWebview(extensionUri);

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
    this.update();
  }

  public dispose(): void {
    TracePanel.currentPanel = undefined;
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
      const trace = await apiClient.traceSymbol(this.symbol);
      if (trace && trace.success) {
        this.panel.webview.postMessage({
          type: 'update',
          data: trace.data,
          symbol: this.symbol,
        });
      }
    } catch (err) {
      console.error('Failed to update trace view:', err);
    }
  }

  private getHtmlForWebview(extensionUri: vscode.Uri): string {
    const webview = this.panel.webview;
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(extensionUri, 'webviews', 'trace', 'trace.js')
    );

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RIP Trace</title>
</head>
<body>
  <div id="content"></div>
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
