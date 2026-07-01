import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { CliExecutor } from './client/cliExecutor';
import { ServerManager } from './client/serverManager';
import { CommandResult, IntentResult } from './sessionManager';

export class ExecutionEngine {
  private readonly cliExecutor = new CliExecutor();

  constructor(private readonly serverManager: ServerManager) {}

  async execute(intent: IntentResult, workspaceRoot: string): Promise<CommandResult> {
    const start = Date.now();
    try {
      const cliResult = await this.executeViaCli(intent, workspaceRoot);
      return { ...cliResult, durationMs: Date.now() - start };
    } catch (cliError) {
      try {
        const apiResult = await this.executeViaHttp(intent, workspaceRoot);
        return { ...apiResult, durationMs: Date.now() - start };
      } catch (httpError) {
        const cliMessage = cliError instanceof Error ? cliError.message : String(cliError);
        const httpMessage = httpError instanceof Error ? httpError.message : String(httpError);
        throw new Error(`CLI and HTTP execution both failed.\n\nCLI:\n${cliMessage}\n\nHTTP:\n${httpMessage}`);
      }
    }
  }

  async executeRawCommand(
    commandLine: string,
    workspaceRoot: string,
    onData?: (chunk: string, stream: 'stdout' | 'stderr') => void
  ): Promise<CommandResult> {
    const start = Date.now();
    const result = await this.cliExecutor.runRepoCommand(commandLine, workspaceRoot, { onData });
    const command = inferCommandFromCommandLine(result.commandLine);
    return {
      command,
      mode: 'cli',
      stdout: stripAnsi(result.stdout),
      stderr: stripAnsi(result.stderr),
      data: parseJson(result.stdout),
      durationMs: Date.now() - start,
      commandLine: result.commandLine,
    };
  }

  private async executeViaCli(
    intent: IntentResult,
    workspaceRoot: string
  ): Promise<Omit<CommandResult, 'durationMs'>> {
    const args = buildCliArgs(intent);
    const result = await this.cliExecutor.runRepo(args, workspaceRoot);
    return {
      command: intent.command,
      mode: 'cli',
      stdout: stripAnsi(result.stdout),
      stderr: stripAnsi(result.stderr),
      data: parseJson(result.stdout),
    };
  }

  private async executeViaHttp(
    intent: IntentResult,
    workspaceRoot: string
  ): Promise<Omit<CommandResult, 'durationMs'>> {
    const apiClient = this.serverManager.getApiClient();
    if (!(await apiClient.isHealthy())) {
      await this.serverManager.startServer();
    }
    await apiClient.assertServerMode();

    const query = String(intent.parameters.query || intent.target || '');
    const projectId = readActiveProjectId(workspaceRoot);
    let data: unknown;
    switch (intent.command) {
      case 'explain':
        data = await apiClient.explain(query, projectId);
        break;
      case 'search':
        data = await apiClient.search(query, projectId);
        break;
      case 'trace':
        data = await apiClient.traceSymbol(query);
        break;
      case 'impact':
        data = await apiClient.impactSymbol(query);
        break;
      case 'architecture':
        data = await apiClient.getArchitecture();
        break;
      case 'metrics':
        data = await apiClient.getMetrics();
        break;
      default:
        throw new Error(`Unsupported command ${intent.command}`);
    }

    return {
      command: intent.command,
      mode: 'http',
      data,
      stdout: JSON.stringify(data, null, 2),
      stderr: `workspace=${workspaceRoot}`,
    };
  }
}

export function isRawRipCommand(query: string): boolean {
  const trimmed = query.trim().replace(/^PS\s+[^>]+>\s*/i, '');
  return /^repo(?:\s|$)/i.test(trimmed) || /^uv\s+run\s+repo(?:\s|$)/i.test(trimmed);
}

function buildCliArgs(intent: IntentResult): string[] {
  const query = String(intent.parameters.query || intent.target || '').trim();
  switch (intent.command) {
    case 'explain':
      return ['explain', query, '--diagram', '--tree', '--deps'];
    case 'search':
      return ['search', query, '--limit', '12'];
    case 'trace':
      return ['trace', query, '--format', 'json'];
    case 'impact':
      return ['impact', query, '--format', 'json'];
    case 'architecture':
      return ['architecture', '--format', 'json'];
    case 'metrics':
      return ['metrics', '--top-risk', '10'];
    default:
      return ['explain', query];
  }
}

function parseJson(stdout: string): unknown | undefined {
  const trimmed = stripAnsi(stdout).trim();
  if (!trimmed) {
    return undefined;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    const match = trimmed.match(/({[\s\S]*}|\[[\s\S]*\])\s*$/);
    if (!match) {
      return undefined;
    }
    try {
      return JSON.parse(match[1]);
    } catch {
      return undefined;
    }
  }
}

function stripAnsi(value: string): string {
  return value.replace(/\u001b\[[0-9;]*m/g, '');
}

function inferCommandFromCommandLine(commandLine: string): Exclude<CommandResult['command'], never> {
  const tokens = commandLine.split(/\s+/).filter(Boolean);
  const repoIndex = tokens.findIndex((token) => token.toLowerCase() === 'repo');
  const subcommand = repoIndex >= 0 ? tokens[repoIndex + 1]?.toLowerCase() : undefined;
  switch (subcommand) {
    case 'search':
      return 'search';
    case 'trace':
      return 'trace';
    case 'impact':
      return 'impact';
    case 'architecture':
      return 'architecture';
    case 'metrics':
      return 'metrics';
    case 'explain':
    default:
      return 'explain';
  }
}

export function getWorkspaceRoot(): string {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    throw new Error('Open a workspace folder before using RIP chat.');
  }
  return folder.uri.fsPath;
}

function readActiveProjectId(workspaceRoot: string): string {
  const activeProjectPath = path.join(workspaceRoot, '.repo-intel', 'active_project');
  try {
    return fs.readFileSync(activeProjectPath, 'utf8').trim();
  } catch {
    return '';
  }
}
