import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/models/sandbox.dart';
import '../../providers/sandbox_provider.dart';

class TerminalView extends ConsumerStatefulWidget {
  const TerminalView({super.key});

  @override
  ConsumerState<TerminalView> createState() => _TerminalViewState();
}

class _TerminalViewState extends ConsumerState<TerminalView> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _focusNode = FocusNode();
  bool _autoScroll = true;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _sendCommand([String? customCommand]) {
    final state = ref.read(sandboxProvider);
    if (!state.isConnected) return;

    final text = (customCommand ?? _controller.text).trim();
    if (text.isEmpty) return;
    ref.read(sandboxProvider.notifier).sendCommand(text);
    if (customCommand == null) {
      _controller.clear();
    }
  }

  void _scrollToBottom() {
    if (!_autoScroll) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  void _copyLogs(List<TerminalOutput> outputs) {
    final fullLog = outputs.map((o) => '${o.type}: ${o.command} ${o.output}').join('\n');
    Clipboard.setData(ClipboardData(text: fullLog));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.check_circle_outline, color: Color(0xFF10B981), size: 18),
            SizedBox(width: 8),
            Text('Terminal logs copied to clipboard'),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        backgroundColor: const Color(0xFF1E1E3F),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final outputs = state.terminalOutputs;
    final env = state.sandbox?.environment ?? 'python';

    if (outputs.isNotEmpty) _scrollToBottom();

    final presets = _getPresetsForEnv(env);

    return Column(
      children: [
        // Terminal Action Header (Log Actions)
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          color: const Color(0xFF0F0F23).withValues(alpha: 0.9),
          child: Row(
            children: [
              const Icon(Icons.terminal_rounded, size: 16, color: Color(0xFF818CF8)),
              const SizedBox(width: 8),
              Text(
                'REAL-TIME TERMINAL OUTPUT (${outputs.length})',
                style: const TextStyle(
                  color: Colors.white54,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.8,
                ),
              ),
              const Spacer(),
              IconButton(
                icon: Icon(
                  _autoScroll ? Icons.arrow_downward_rounded : Icons.pause_rounded,
                  color: _autoScroll ? const Color(0xFF10B981) : Colors.white38,
                  size: 16,
                ),
                tooltip: _autoScroll ? 'Auto-scroll active' : 'Auto-scroll paused',
                onPressed: () => setState(() => _autoScroll = !_autoScroll),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
              const SizedBox(width: 12),
              IconButton(
                icon: const Icon(Icons.copy_rounded, color: Colors.white54, size: 16),
                tooltip: 'Copy Logs',
                onPressed: () => _copyLogs(outputs),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
              const SizedBox(width: 12),
              IconButton(
                icon: const Icon(Icons.delete_outline_rounded, color: Colors.white54, size: 16),
                tooltip: 'Clear Terminal',
                onPressed: () => ref.read(sandboxProvider.notifier).clearTerminal(),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
            ],
          ),
        ),

        // Disconnected Banner
        if (!state.isConnected && state.sandbox != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            color: Colors.redAccent.withValues(alpha: 0.15),
            child: Row(
              children: [
                const Icon(Icons.wifi_off_rounded, color: Colors.redAccent, size: 16),
                const SizedBox(width: 8),
                const Text(
                  'Terminal connection lost.',
                  style: TextStyle(color: Colors.redAccent, fontSize: 12, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: () => ref.read(sandboxProvider.notifier).reconnectTerminal(state.sandbox!.id),
                  icon: const Icon(Icons.refresh_rounded, size: 14),
                  label: const Text('Reconnect'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.redAccent,
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                  ),
                ),
              ],
            ),
          ),

        // Terminal Output Stream View
        Expanded(
          child: Container(
            color: const Color(0xFF0A0A16),
            child: outputs.isEmpty
                ? _EmptyTerminalState(
                    env: env,
                    onSelectPreset: (cmd) => _sendCommand(cmd),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
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

        // Command Preset Chips Bar
        Container(
          color: const Color(0xFF0F0F23),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            physics: const BouncingScrollPhysics(),
            child: Row(
              children: [
                const Text(
                  'PRESETS: ',
                  style: TextStyle(color: Colors.white38, fontSize: 10, fontWeight: FontWeight.bold),
                ),
                ...presets.map((cmd) => Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: ActionChip(
                        label: Text(
                          cmd,
                          style: const TextStyle(
                            color: Color(0xFFC7D2FE),
                            fontSize: 11,
                            fontFamily: 'monospace',
                          ),
                        ),
                        backgroundColor: const Color(0xFF1E1E3F),
                        side: BorderSide(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        visualDensity: VisualDensity.compact,
                        onPressed: () => _sendCommand(cmd),
                      ),
                    )),
              ],
            ),
          ),
        ),

        // Mobile-Dev Keyboard Toolbar
        Container(
          color: const Color(0xFF0F0F23).withValues(alpha: 0.95),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(
            children: [
              _DevKey(
                label: 'Esc', 
                onPressed: () => ref.read(sandboxProvider.notifier).sendCommand('\x1b')
              ),
              const SizedBox(width: 6),
              _DevKey(
                label: 'Ctrl+C', 
                onPressed: () => ref.read(sandboxProvider.notifier).sendCommand('\x03')
              ),
              const SizedBox(width: 6),
              _DevKey(
                label: 'Tab', 
                onPressed: () => ref.read(sandboxProvider.notifier).sendCommand('\t')
              ),
              const Spacer(),
              _DevKey(
                icon: Icons.arrow_upward_rounded, 
                onPressed: () => ref.read(sandboxProvider.notifier).sendCommand('\x1b[A')
              ),
              const SizedBox(width: 6),
              _DevKey(
                icon: Icons.arrow_downward_rounded, 
                onPressed: () => ref.read(sandboxProvider.notifier).sendCommand('\x1b[B')
              ),
            ],
          ),
        ),

        // Glassmorphic Floating Command Input Bar
        ClipRRect(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFF13132B).withValues(alpha: 0.9),
                border: Border(
                  top: BorderSide(
                    color: const Color(0xFF6366F1).withValues(alpha: 0.25),
                    width: 1,
                  ),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.42),
                    blurRadius: 16,
                    offset: const Offset(0, -4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFF10B981).withValues(alpha: 0.3)),
                    ),
                    child: const Text(
                      '\$',
                      style: TextStyle(
                        color: Color(0xFF10B981),
                        fontFamily: 'monospace',
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                      child: TextField(
                        controller: _controller,
                        focusNode: _focusNode,
                        enabled: state.isConnected,
                        style: TextStyle(
                          color: state.isConnected ? Colors.white : Colors.white38,
                          fontFamily: 'monospace',
                          fontSize: 13,
                        ),
                        decoration: InputDecoration(
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          filled: false,
                          hintText: state.isConnected 
                              ? 'Type bash command or select template preset...' 
                              : 'Terminal disconnected. Reconnect to send commands...',
                          hintStyle: const TextStyle(
                            color: Colors.white38,
                            fontFamily: 'monospace',
                            fontSize: 12,
                          ),
                          contentPadding: EdgeInsets.zero,
                        ),
                        onSubmitted: (_) => _sendCommand(),
                      ),
                  ),
                  const SizedBox(width: 8),
                  InkWell(
                    onTap: state.isConnected ? () => _sendCommand() : null,
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: state.isConnected 
                              ? const [Color(0xFF6366F1), Color(0xFF4F46E5)]
                              : [const Color(0xFF6366F1).withValues(alpha: 0.3), const Color(0xFF4F46E5).withValues(alpha: 0.3)],
                        ),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: state.isConnected ? [
                          BoxShadow(
                            color: const Color(0xFF6366F1).withValues(alpha: 0.4),
                            blurRadius: 8,
                          ),
                        ] : [],
                      ),
                      child: Icon(
                        Icons.send_rounded,
                        color: state.isConnected ? Colors.white : Colors.white54,
                        size: 16,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  List<String> _getPresetsForEnv(String env) {
    final lower = env.toLowerCase();
    if (lower.contains('python')) {
      return ['python --version', 'pip list', 'python -c "print(\'Hello RIP\')"', 'pytest'];
    } else if (lower.contains('node')) {
      return ['node -v', 'npm list', 'npm run build', 'node -e "console.log(process.version)"'];
    } else if (lower.contains('go')) {
      return ['go version', 'go env', 'go run main.go', 'go test ./...'];
    } else if (lower.contains('rust')) {
      return ['rustc --version', 'cargo --version', 'cargo check', 'cargo build'];
    } else if (lower.contains('flutter')) {
      return ['flutter --version', 'flutter analyze', 'dart --version'];
    }
    return ['uname -a', 'ls -la', 'pwd', 'top -b -n 1', 'git status'];
  }
}

class _EmptyTerminalState extends StatelessWidget {
  final String env;
  final Function(String) onSelectPreset;

  const _EmptyTerminalState({required this.env, required this.onSelectPreset});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                shape: BoxShape.circle,
                border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
              ),
              child: const Icon(Icons.terminal_rounded, color: Color(0xFF818CF8), size: 36),
            ),
            const SizedBox(height: 16),
            Text(
              'Terminal Session Ready (${env.toUpperCase()})',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 15,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Execute commands or select a preset below to start streaming output logs.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.5),
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TerminalLine extends StatelessWidget {
  final TerminalOutput output;
  const _TerminalLine({required this.output});

  @override
  Widget build(BuildContext context) {
    Color color;
    IconData? icon;

    switch (output.type) {
      case 'command_start':
        color = const Color(0xFF10B981);
        icon = Icons.play_arrow_rounded;
        break;
      case 'command_blocked':
        color = Colors.redAccent;
        icon = Icons.block_rounded;
        break;
      case 'command_error':
        color = Colors.redAccent;
        icon = Icons.error_outline_rounded;
        break;
      case 'approval_needed':
        color = Colors.amber;
        icon = Icons.warning_amber_rounded;
        break;
      case 'command_rejected':
        color = Colors.orangeAccent;
        icon = Icons.cancel_outlined;
        break;
      default:
        color = const Color(0xFFCBD5E1);
        icon = null;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (output.type == 'command_start' || output.command.isNotEmpty)
            Row(
              children: [
                if (icon != null) Icon(icon, color: color, size: 14),
                if (icon != null) const SizedBox(width: 6),
                const Text(
                  '\$ ',
                  style: TextStyle(
                    color: Color(0xFF10B981),
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
                Expanded(
                  child: SelectableText(
                    output.command,
                    style: TextStyle(
                      color: color,
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.w600,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          if (output.output.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: SelectableText(
                output.output,
                style: const TextStyle(
                  color: Color(0xFFE2E8F0),
                  fontFamily: 'monospace',
                  fontSize: 12,
                  height: 1.3,
                ),
              ),
            ),
          if (output.error != null && output.error!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: SelectableText(
                output.error!,
                style: const TextStyle(
                  color: Colors.redAccent,
                  fontFamily: 'monospace',
                  fontSize: 12,
                ),
              ),
            ),
          if (output.exitCode != 0 && output.type == 'command_output')
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                'exit code: ${output.exitCode} (${output.durationMs}ms)',
                style: const TextStyle(
                  color: Colors.white38,
                  fontFamily: 'monospace',
                  fontSize: 10,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ApprovalBanner extends StatelessWidget {
  final String command;
  final String reason;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApprovalBanner({
    required this.command,
    required this.reason,
    required this.onApprove,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.12),
        border: Border.all(color: Colors.amber.withValues(alpha: 0.6)),
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.amber.withValues(alpha: 0.1),
            blurRadius: 12,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.shield_outlined, color: Colors.amber, size: 18),
              SizedBox(width: 8),
              Text(
                'Execution Approval Required',
                style: TextStyle(
                  color: Colors.amber,
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.42),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              command,
              style: const TextStyle(
                color: Colors.white,
                fontFamily: 'monospace',
                fontSize: 12,
              ),
            ),
          ),
          if (reason.isNotEmpty) const SizedBox(height: 6),
          if (reason.isNotEmpty)
            Text(
              reason,
              style: const TextStyle(color: Colors.white70, fontSize: 11),
            ),
          const SizedBox(height: 12),
          Row(
            children: [
              ElevatedButton.icon(
                onPressed: onApprove,
                icon: const Icon(Icons.check, size: 16),
                label: const Text('Approve'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF10B981),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              OutlinedButton.icon(
                onPressed: onReject,
                icon: const Icon(Icons.close, size: 16),
                label: const Text('Reject'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.redAccent,
                  side: const BorderSide(color: Colors.redAccent),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _DevKey extends StatelessWidget {
  final String? label;
  final IconData? icon;
  final VoidCallback onPressed;

  const _DevKey({this.label, this.icon, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(6),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: const Color(0xFF1E1E3F),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
          ),
          child: icon != null
              ? Icon(icon, color: const Color(0xFFC7D2FE), size: 14)
              : Text(
                  label!,
                  style: const TextStyle(
                    color: Color(0xFFC7D2FE),
                    fontSize: 11,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w600,
                  ),
                ),
        ),
      ),
    );
  }
}

