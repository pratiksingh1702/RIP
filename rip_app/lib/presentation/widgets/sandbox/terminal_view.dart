import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/models/sandbox.dart';
import '../../providers/sandbox_provider.dart';

class TerminalView extends ConsumerStatefulWidget {
  const TerminalView({super.key});

  @override
  ConsumerState<TerminalView> createState() => _TerminalViewState();
}

class _TerminalViewState extends ConsumerState<TerminalView> {
  final _scrollController = ScrollController();
  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _sendCommand([String? customCommand]) {
    final state = ref.read(sandboxProvider);
    if (!state.isConnected) return;

    final text = (customCommand ?? '').trim();
    if (text.isEmpty) return;
    ref.read(sandboxProvider.notifier).sendCommand(text);
  }

  void _scrollToBottom() {
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



  @override
  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final outputs = state.terminalOutputs;
    final env = state.sandbox?.environment ?? 'python';
    final isExecuting = state.isExecuting;
    final executingCommand = state.executingCommand ?? '';

    if (outputs.isNotEmpty || isExecuting) _scrollToBottom();

    final presets = _getPresetsForEnv(env);

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? Colors.black : Theme.of(context).scaffoldBackgroundColor;

    return Stack(
      children: [
        // Terminal Output Stream View (placed first so it renders behind everything)
        Positioned.fill(
          child: Container(
            color: bgColor,
            child: ListView.builder(
              controller: _scrollController,
              padding: EdgeInsets.fromLTRB(16, MediaQuery.paddingOf(context).top + 76, 16, MediaQuery.paddingOf(context).bottom + 200),
              itemCount: outputs.length + 1,
              itemBuilder: (context, index) {
                if (index < outputs.length) {
                  return _TerminalLine(output: outputs[index]);
                }
                
                if (state.pendingApproval != null) {
                  return _ApprovalBanner(
                    command: state.pendingApproval!.command,
                    reason: state.pendingApproval!.reason ?? '',
                    onApprove: () => ref.read(sandboxProvider.notifier).approveCommand(state.pendingApproval!.command),
                    onReject: () => ref.read(sandboxProvider.notifier).rejectCommand(state.pendingApproval!.command),
                  );
                }
                
                if (isExecuting) {
                  final lastOutputText = outputs.isNotEmpty ? outputs.last.output : '';
                  if (_isInteractivePrompt(lastOutputText)) {
                    return _InteractivePromptButtons(
                      onResponse: (resp) => _sendCommand(resp),
                    );
                  }
                  return _TerminalWaitingLoader(command: executingCommand);
                }
                
                return _InlineTerminalPrompt(
                  onSubmitted: (cmd) => _sendCommand(cmd),
                );
              },
            ),
          ),
        ),

        // Top Fade Overlay (for terminal text scrolling behind app bar)
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          height: 120,
          child: IgnorePointer(
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    bgColor.withValues(alpha: 0.95),
                    bgColor.withValues(alpha: 0.6),
                    bgColor.withValues(alpha: 0.0),
                  ],
                  stops: const [0.0, 0.4, 1.0],
                ),
              ),
            ),
          ),
        ),

        // Disconnected Banner
        if (!state.isConnected && state.sandbox != null)
          Positioned(
            bottom: 100,
            left: 16,
            right: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.redAccent,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.redAccent.withValues(alpha: 0.3)),
              ),
              child: Row(
              children: [
                const Icon(Icons.wifi_off_rounded, color: Colors.white, size: 16),
                const SizedBox(width: 8),
                const Text(
                  'Terminal connection lost.',
                  style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: () => ref.read(sandboxProvider.notifier).reconnectTerminal(state.sandbox!.id),
                  icon: const Icon(Icons.refresh_rounded, size: 14),
                  label: const Text('Reconnect'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.white,
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                  ),
                ),
              ],
            ),
          ),
        ),

        // Bottom Fade Overlay
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          height: 180,
          child: IgnorePointer(
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    bgColor.withValues(alpha: 0.0),
                    bgColor.withValues(alpha: 0.6),
                    bgColor.withValues(alpha: 0.95),
                  ],
                  stops: const [0.0, 0.4, 1.0],
                ),
              ),
            ),
          ),
        ),

        // Separate Floating Glassmorphic Preset Chips
        Align(
          alignment: Alignment.bottomCenter,
          child: Padding(
            padding: EdgeInsets.only(
              bottom: MediaQuery.paddingOf(context).bottom + 20,
              left: 16,
              right: isExecuting ? 116 : 16,
            ),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              child: Row(
                children: presets.map((cmd) {
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: BackdropFilter(
                        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                        child: Material(
                          color: Colors.transparent,
                          child: InkWell(
                            onTap: () => _sendCommand(cmd),
                            borderRadius: BorderRadius.circular(16),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                              decoration: BoxDecoration(
                                color: isDark
                                    ? Colors.white.withValues(alpha: 0.08)
                                    : Colors.black.withValues(alpha: 0.05),
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: isDark
                                      ? Colors.white.withValues(alpha: 0.12)
                                      : Colors.black.withValues(alpha: 0.1),
                                ),
                              ),
                              child: Text(
                                cmd,
                                style: TextStyle(
                                  color: isDark ? const Color(0xFFC7D2FE) : Colors.black87,
                                  fontSize: 12,
                                  fontFamily: 'monospace',
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ),

        // Floating Ctrl+C Component at Bottom Right Corner when running command
        if (isExecuting)
          Positioned(
            bottom: MediaQuery.paddingOf(context).bottom + 20,
            right: 16,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: () => ref.read(sandboxProvider.notifier).sendCommand('\x03'),
                    borderRadius: BorderRadius.circular(16),
                    child: Container(
                      height: 36,
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      decoration: BoxDecoration(
                        color: Colors.redAccent.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: Colors.redAccent.withValues(alpha: 0.4),
                        ),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.stop_circle_outlined, color: Colors.redAccent, size: 16),
                          SizedBox(width: 6),
                          Text(
                            'Ctrl+C',
                            style: TextStyle(
                              color: Colors.redAccent,
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
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

  bool _isInteractivePrompt(String output) {
    return RegExp(r'\[y/N\]|\[Y/n\]|›|\? $|\(yes/no\)').hasMatch(output.trim());
  }
}

class _InteractivePromptButtons extends StatelessWidget {
  final Function(String) onResponse;
  const _InteractivePromptButtons({required this.onResponse});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 8),
      child: Row(
        children: [
          _QuickResponseButton(label: "Yes", onTap: () => onResponse("y\n")),
          const SizedBox(width: 8),
          _QuickResponseButton(label: "No", onTap: () => onResponse("n\n")),
          const SizedBox(width: 8),
          _QuickResponseButton(label: "Continue", onTap: () => onResponse("\n")),
        ],
      ),
    );
  }
}

class _QuickResponseButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _QuickResponseButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      label: Text(
        label,
        style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 11, fontWeight: FontWeight.bold),
      ),
      backgroundColor: Theme.of(context).brightness == Brightness.dark ? const Color(0xFF1E1E3F) : Colors.grey.shade100,
      side: BorderSide(color: const Color(0xFF6366F1).withValues(alpha: 0.5)),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      onPressed: onTap,
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
        color = Theme.of(context).brightness == Brightness.dark ? const Color(0xFFCBD5E1) : Colors.black87;
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
                style: TextStyle(
                  color: Theme.of(context).brightness == Brightness.dark ? const Color(0xFFE2E8F0) : Colors.black87,
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
              style: TextStyle(
                        color: Theme.of(context).brightness == Brightness.dark ? Colors.white : Colors.black87,
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


class _TerminalWaitingLoader extends StatefulWidget {
  final String command;
  const _TerminalWaitingLoader({required this.command});

  @override
  State<_TerminalWaitingLoader> createState() => _TerminalWaitingLoaderState();
}
class _TerminalWaitingLoaderState extends State<_TerminalWaitingLoader>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animationController,
      builder: (context, child) {
        // Subtle vertical bounce
        final dy = -6.0 * _animationController.value;

        return Container(
          margin: const EdgeInsets.only(top: 12, bottom: 24, left: 4),
          alignment: Alignment.centerLeft,
          child: Transform.translate(
            offset: Offset(0, dy),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Image.asset(
                  'assets/mascot/typing.png',
                  width: 28,
                  height: 28,
                  filterQuality: FilterQuality.high,
                ),
                const SizedBox(width: 8),
                Text(
                  'executing...',
                  style: TextStyle(
                    color: Theme.of(context).brightness == Brightness.dark ? Colors.white38 : Colors.black38,
                    fontSize: 11,
                    fontFamily: 'monospace',
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

}


class _InlineTerminalPrompt extends StatefulWidget {
  final Function(String) onSubmitted;
  const _InlineTerminalPrompt({required this.onSubmitted});

  @override
  State<_InlineTerminalPrompt> createState() => _InlineTerminalPromptState();
}

class _InlineTerminalPromptState extends State<_InlineTerminalPrompt> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _controller.text.trim();
    if (text.isNotEmpty) {
      widget.onSubmitted(text);
      _controller.clear();
    }
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.only(bottom: 6),
      child: TextField(
        controller: _controller,
        focusNode: _focusNode,
        autofocus: true,
        style: TextStyle(
          color: isDark ? Colors.white : Colors.black87,
          fontFamily: 'monospace',
          fontSize: 13,
        ),
        cursorColor: isDark ? Colors.white70 : Colors.black87,
        cursorWidth: 2,
   decoration: InputDecoration(
  hintText: 'Write your cmnd...',
  hintStyle: TextStyle(
    color: isDark ? Colors.white38 : Colors.black38,
    fontFamily: 'monospace',
    fontSize: 13,
  ),
  isCollapsed: true, // removes default padding/min-height, not just isDense
  filled: false,
  fillColor: Colors.transparent,
  border: InputBorder.none,
  enabledBorder: InputBorder.none,
  focusedBorder: InputBorder.none,
  disabledBorder: InputBorder.none,
  errorBorder: InputBorder.none,
  focusedErrorBorder: InputBorder.none,
),
        onSubmitted: (_) => _submit(),
      ),
    );
  }
}
