import * as cp from 'child_process';

export interface CliExecutionResult {
  stdout: string;
  stderr: string;
  commandLine: string;
}

export interface CliExecutionOptions {
  timeoutMs?: number;
  onData?: (chunk: string, stream: 'stdout' | 'stderr') => void;
}

export class CliExecutor {
  async isAvailable(cwd: string): Promise<boolean> {
    try {
      await this.execFile('uv', ['run', 'repo', '--help'], cwd, 15000);
      return true;
    } catch {
      try {
        await this.execFile('repo', ['--help'], cwd, 15000);
        return true;
      } catch {
        return false;
      }
    }
  }

  async runRepo(args: string[], cwd: string, timeoutMs = 120000): Promise<CliExecutionResult> {
    try {
      const result = await this.execFile('uv', ['run', 'repo', ...args], cwd, timeoutMs);
      return { ...result, commandLine: `uv run repo ${args.join(' ')}` };
    } catch (uvError) {
      try {
        const result = await this.execFile('repo', args, cwd, timeoutMs);
        return { ...result, commandLine: `repo ${args.join(' ')}` };
      } catch (repoError) {
        const uvMessage = uvError instanceof Error ? uvError.message : String(uvError);
        const repoMessage = repoError instanceof Error ? repoError.message : String(repoError);
        throw new Error(`RIP CLI failed.\nuv run repo: ${uvMessage}\nrepo: ${repoMessage}`);
      }
    }
  }

  async runRepoCommand(
    commandLine: string,
    cwd: string,
    options: CliExecutionOptions = {}
  ): Promise<CliExecutionResult> {
    const parsed = parseRepoCommand(commandLine);
    if (!parsed) {
      throw new Error('Only RIP CLI commands are supported here. Try `repo explain "How typeProvider works" --diagram`.');
    }
    const timeoutMs = options.timeoutMs ?? 180000;

    if (parsed.runner === 'uv') {
      const result = await this.spawnFile('uv', ['run', 'repo', ...parsed.args], cwd, timeoutMs, options.onData);
      return { ...result, commandLine: `uv run repo ${formatArgs(parsed.args)}`.trim() };
    }

    const result = await this.spawnFile('repo', parsed.args, cwd, timeoutMs, options.onData);
    return { ...result, commandLine: `repo ${formatArgs(parsed.args)}`.trim() };
  }

  private execFile(
    command: string,
    args: string[],
    cwd: string,
    timeoutMs: number
  ): Promise<Omit<CliExecutionResult, 'commandLine'>> {
    return new Promise((resolve, reject) => {
      cp.execFile(
        command,
        args,
        {
          cwd,
          timeout: timeoutMs,
          windowsHide: true,
          maxBuffer: 10 * 1024 * 1024,
        },
        (error, stdout, stderr) => {
          if (error) {
            const message = stderr?.trim() || stdout?.trim() || error.message;
            reject(new Error(message));
            return;
          }
          resolve({ stdout, stderr });
        }
      );
    });
  }

  private spawnFile(
    command: string,
    args: string[],
    cwd: string,
    timeoutMs: number,
    onData?: (chunk: string, stream: 'stdout' | 'stderr') => void
  ): Promise<Omit<CliExecutionResult, 'commandLine'>> {
    return new Promise((resolve, reject) => {
      let stdout = '';
      let stderr = '';
      let settled = false;
      const child = cp.spawn(command, args, {
        cwd,
        shell: false,
        windowsHide: true,
      });

      const timer = setTimeout(() => {
        if (settled) {
          return;
        }
        settled = true;
        child.kill();
        reject(new Error(`Command timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      child.stdout?.on('data', (data: Buffer) => {
        const text = data.toString();
        stdout += text;
        onData?.(text, 'stdout');
      });

      child.stderr?.on('data', (data: Buffer) => {
        const text = data.toString();
        stderr += text;
        onData?.(text, 'stderr');
      });

      child.on('error', (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(error);
      });

      child.on('close', (code) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        if (code && code !== 0) {
          reject(new Error(stderr.trim() || stdout.trim() || `Command exited with code ${code}`));
          return;
        }
        resolve({ stdout, stderr });
      });
    });
  }
}

function parseRepoCommand(commandLine: string): { runner: 'repo' | 'uv'; args: string[] } | undefined {
  const tokens = tokenizeCommand(commandLine.trim().replace(/^PS\s+[^>]+>\s*/i, ''));
  if (tokens.length === 0) {
    return undefined;
  }

  const head = tokens[0].toLowerCase();
  if (head === 'repo') {
    return { runner: 'repo', args: tokens.slice(1) };
  }
  if (head === 'uv' && tokens[1]?.toLowerCase() === 'run' && tokens[2]?.toLowerCase() === 'repo') {
    return { runner: 'uv', args: tokens.slice(3) };
  }
  return undefined;
}

function tokenizeCommand(commandLine: string): string[] {
  const tokens: string[] = [];
  let current = '';
  let quote: '"' | "'" | undefined;
  let escaping = false;

  for (const char of commandLine) {
    if (escaping) {
      current += char;
      escaping = false;
      continue;
    }
    if (char === '\\' && quote === '"') {
      escaping = true;
      continue;
    }
    if ((char === '"' || char === "'") && (!quote || quote === char)) {
      quote = quote ? undefined : char;
      continue;
    }
    if (!quote && /\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = '';
      }
      continue;
    }
    current += char;
  }

  if (current) {
    tokens.push(current);
  }
  return tokens;
}

function formatArgs(args: string[]): string {
  return args.map((arg) => (/\s/.test(arg) ? `"${arg.replace(/"/g, '\\"')}"` : arg)).join(' ');
}
