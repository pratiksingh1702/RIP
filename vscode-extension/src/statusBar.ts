import * as vscode from 'vscode';
import { ServerManager } from './client/serverManager';

export class RipStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;
  private timer: NodeJS.Timeout | undefined;

  constructor(private readonly serverManager: ServerManager) {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 90);
    this.item.command = 'rip.checkStatus';
    this.item.text = 'RIP: checking';
    this.item.tooltip = 'Check RIP indexing status';
    this.item.show();
    this.timer = setInterval(() => void this.refresh(), 30000);
    void this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      const api = this.serverManager.getApiClient();
      const status = await api.getIndexStatus();
      const data = status?.data || {};
      const count = data.entity_count ?? data.total_entities ?? 0;
      const state = data.status || 'ready';
      this.item.text = state === 'ready' ? `RIP: ${count} entities` : `RIP: ${state}`;
      this.item.tooltip = `RIP index status: ${state}`;
      this.item.backgroundColor = undefined;
    } catch {
      this.item.text = 'RIP: CLI ready';
      this.item.tooltip = 'RIP server is offline; chat will use the CLI first.';
      this.item.backgroundColor = undefined;
    }
  }

  dispose(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
    this.item.dispose();
  }
}
