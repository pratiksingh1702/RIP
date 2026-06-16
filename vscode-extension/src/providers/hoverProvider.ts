import * as vscode from 'vscode';
import { ServerManager } from '../client/serverManager';

export class HoverProvider implements vscode.HoverProvider {
  private serverManager: ServerManager;

  constructor(serverManager: ServerManager) {
    this.serverManager = serverManager;
  }

  async provideHover(
    document: vscode.TextDocument,
    position: vscode.Position,
    token: vscode.CancellationToken
  ): Promise<vscode.Hover | undefined> {
    try {
      const apiClient = this.serverManager.getApiClient();
      const word = document.getText(document.getWordRangeAtPosition(position));
      
      // Try to get explanation for symbol
      const explanation = await apiClient.explainSymbol(word);
      if (explanation && explanation.success && explanation.data) {
        const content = new vscode.MarkdownString(
          `**RIP Analysis**\n\n${explanation.data.explanation}`
        );
        content.isTrusted = true;
        return new vscode.Hover(content);
      }
    } catch (err) {
      // Just fall through to no hover from RIP
      console.debug('RIP hover lookup failed:', err);
    }
    return undefined;
  }
}
