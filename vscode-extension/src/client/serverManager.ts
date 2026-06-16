import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { ApiClient } from './apiClient';

export class ServerManager {
  private serverProcess: cp.ChildProcess | null = null;
  private apiClient: ApiClient | null = null;
  private readonly outputChannel: vscode.OutputChannel;

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

    const config = vscode.workspace.getConfiguration('repoIntel');
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

      this.serverProcess = cp.spawn(serverPath, ['run', 'rip', 'server'], {
        cwd,
        shell: true,
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

      // Wait for server to be ready
      await new Promise(resolve => setTimeout(resolve, 2000));
      this.outputChannel.appendLine('RIP server started successfully');
    } catch (err) {
      this.outputChannel.appendLine(`Failed to start RIP server: ${err}`);
      vscode.window.showErrorMessage(`Failed to start RIP server: ${err}`);
    }
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
