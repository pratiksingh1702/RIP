import * as vscode from 'vscode';
import { ServerManager } from '../client/serverManager';

export class CodeActionProvider implements vscode.CodeActionProvider {
  private serverManager: ServerManager;

  constructor(serverManager: ServerManager) {
    this.serverManager = serverManager;
  }

  provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
    token: vscode.CancellationToken
  ): vscode.ProviderResult<(vscode.CodeAction | vscode.Command)[]> {
    const actions: vscode.CodeAction[] = [];

    const wordRange = document.getWordRangeAtPosition(range.start);
    if (wordRange) {
      const traceAction = new vscode.CodeAction('RIP: Trace Symbol', vscode.CodeActionKind.Refactor);
      traceAction.command = {
        command: 'rip.trace',
        title: 'Trace Symbol',
        arguments: [document.getText(wordRange)],
      };
      actions.push(traceAction);

      const impactAction = new vscode.CodeAction('RIP: Impact Analysis', vscode.CodeActionKind.Refactor);
      impactAction.command = {
        command: 'rip.impact',
        title: 'Impact Analysis',
        arguments: [document.getText(wordRange)],
      };
      actions.push(impactAction);

      const explainAction = new vscode.CodeAction('RIP: Explain Symbol', vscode.CodeActionKind.Refactor);
      explainAction.command = {
        command: 'rip.explain',
        title: 'Explain Symbol',
        arguments: [document.getText(wordRange)],
      };
      actions.push(explainAction);
    }

    return actions;
  }
}
