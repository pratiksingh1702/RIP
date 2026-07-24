import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/sandbox.dart';
import '../providers/sandbox_provider.dart';

class TerminalView extends ConsumerStatefulWidget {
  const TerminalView({super.key});

  @override
  ConsumerState<TerminalView> createState() => _TerminalViewState();
}

class _TerminalViewState extends ConsumerState<TerminalView> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _focusNode = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _sendCommand() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    ref.read(sandboxProvider.notifier).sendCommand(text);
    _controller.clear();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 100),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final outputs = state.terminalOutputs;

    if (outputs.isNotEmpty) _scrollToBottom();

    return Column(
      children: [
        // Terminal output area
        Expanded(
          child: Container(
            color: const Color(0xFF1A1A2E),
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              itemCount: outputs.length + (state.pendingApproval != null ? 1 : 0),
              itemBuilder: (context, index) {
                if (state.pendingApproval != null && index == outputs.length) {
                  return _ApprovalBanner(
                    command: state.pendingApproval!.command,
                    reason: state.pendingApproval!.reason ?? '',
                    onApprove: () => ref.read(sandboxProvider.notifier).approveCommand(state.pendingApproval!.command),
                    onReject: () => ref.read(sandboxProvider.notifier).rejectCommand(state.pendingApproval!.command),
                  );
                }
                return _TerminalLine(output: outputs[index]);
              },
            ),
          ),
        ),
        // Input bar
        Container(
          color: const Color(0xFF16213E),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              const Text('\$ ', style: TextStyle(color: Color(0xFF00FF88), fontFamily: 'monospace', fontSize: 16)),
              Expanded(
                child: TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    hintText: 'Type a command...',
                    hintStyle: TextStyle(color: Colors.white38, fontFamily: 'monospace'),
                    contentPadding: EdgeInsets.zero,
                  ),
                  onSubmitted: (_) => _sendCommand(),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.send, color: Color(0xFF00FF88), size: 20),
                onPressed: _sendCommand,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _TerminalLine extends StatelessWidget {
  final TerminalOutput output;
  const _TerminalLine({required this.output});

  @override
  Widget build(BuildContext context) {
    Color color;
    String prefix;

    switch (output.type) {
      case 'command_start':
        color = const Color(0xFF00FF88);
        prefix = '\$ ';
        break;
      case 'command_blocked':
        color = Colors.red;
        prefix = '🚫 ';
        break;
      case 'command_error':
        color = Colors.red;
        prefix = '❌ ';
        break;
      case 'approval_needed':
        color = Colors.amber;
        prefix = '⚠️ ';
        break;
      case 'command_rejected':
        color = Colors.orange;
        prefix = '✋ ';
        break;
      default:
        color = Colors.white70;
        prefix = '';
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: SelectableText.rich(
        TextSpan(
          children: [
            if (prefix.isNotEmpty) TextSpan(text: prefix, style: TextStyle(color: color, fontFamily: 'monospace', fontSize: 13)),
            if (output.type == 'command_start' || output.type == 'command_blocked')
              TextSpan(text: '${output.command}\n', style: TextStyle(color: color, fontFamily: 'monospace', fontSize: 13)),
            if (output.output.isNotEmpty)
              TextSpan(text: output.output, style: const TextStyle(color: Colors.white70, fontFamily: 'monospace', fontSize: 13)),
            if (output.error != null)
              TextSpan(text: '\n${output.error}', style: const TextStyle(color: Colors.red, fontFamily: 'monospace', fontSize: 13)),
            if (output.exitCode != 0 && output.type == 'command_output')
              TextSpan(text: '\nexit code: ${output.exitCode} (${output.durationMs}ms)', style: const TextStyle(color: Colors.white38, fontFamily: 'monospace', fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

class _ApprovalBanner extends StatelessWidget {
  final String command;
  final String reason;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApprovalBanner({required this.command, required this.reason, required this.onApprove, required this.onReject});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.1),
        border: Border.all(color: Colors.amber),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.warning_amber, color: Colors.amber, size: 18),
            SizedBox(width: 8),
            Text('Approval Required', style: TextStyle(color: Colors.amber, fontWeight: FontWeight.bold)),
          ]),
          const SizedBox(height: 8),
          Text(command, style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 13)),
          Text(reason, style: const TextStyle(color: Colors.white54, fontSize: 12)),
          const SizedBox(height: 8),
          Row(children: [
            ElevatedButton(
              onPressed: onApprove,
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
              child: const Text('Approve'),
            ),
            const SizedBox(width: 8),
            OutlinedButton(
              onPressed: onReject,
              style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('Reject'),
            ),
          ]),
        ],
      ),
    );
  }
}
