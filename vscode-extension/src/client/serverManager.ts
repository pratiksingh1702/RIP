import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { ApiClient } from './apiClient';

export class ServerManager {
  private serverProcess: cp.ChildProcess | null = null;
  private apiClient: ApiClient | null = null;
  private readonly outputChannel: vscode.OutputChannel;
  private readonly healthPollIntervalMs = 1000;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('RIP Server');
  }

  getApiClient(): ApiClient {
    if (!this.apiClient) {
      this.apiClient = new ApiClient();
    }
    return this.apiClient;
  }

  async startServer(): Promise<void> {
    if (this.serverProcess) {
      this.outputChannel.appendLine('RIP server already running');
      return;
    }

    const config = vscode.workspace.getConfiguration('rip');
    const autoStart = config.get<boolean>('autoStartServer', true);
    const serverPath = config.get<string>('serverPath', 'uv');

    if (!autoStart) {
      this.outputChannel.appendLine('Auto-start disabled. Please start server manually.');
      return;
    }

    try {
      this.outputChannel.appendLine('Starting RIP server...');
      
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      const cwd = workspaceFolder?.uri.fsPath || process.cwd();

      this.serverProcess = cp.spawn(serverPath, ['run', 'repo', 'serve'], {
        cwd,
        shell: false,
        windowsHide: true,
      });

      this.serverProcess.stdout?.on('data', (data) => {
        this.outputChannel.appendLine(data.toString());
      });

      this.serverProcess.stderr?.on('data', (data) => {
        this.outputChannel.appendLine(data.toString());
      });

      this.serverProcess.on('close', (code) => {
        this.outputChannel.appendLine(`RIP server stopped with code ${code}`);
        this.serverProcess = null;
      });

      await this.waitForServer();
      this.outputChannel.appendLine('RIP server started successfully');
    } catch (err) {
      if (this.serverProcess) {
        this.serverProcess.kill();
        this.serverProcess = null;
      }
      this.outputChannel.appendLine(`Failed to start RIP server: ${err}`);
      vscode.window.showErrorMessage(`Failed to start RIP server: ${err}`);
    }
  }

  private async waitForServer(maxRetries: number = 30): Promise<void> {
    const apiClient = this.getApiClient();
    for (let i = 0; i < maxRetries; i++) {
      if (await apiClient.isHealthy()) {
        return;
      }
      await new Promise(resolve => setTimeout(resolve, this.healthPollIntervalMs));
    }
    throw new Error('Server failed to start');
  }

  async stopServer(): Promise<void> {
    if (!this.serverProcess) {
      return;
    }
    this.serverProcess.kill();
    this.serverProcess = null;
    this.outputChannel.appendLine('RIP server stopped');
  }

  dispose(): void {
    this.stopServer();
    this.outputChannel.dispose();
  }
}
