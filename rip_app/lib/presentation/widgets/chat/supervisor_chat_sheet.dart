import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:rip_app/presentation/providers/supervisor_provider.dart';

class SupervisorChatSheet extends ConsumerStatefulWidget {
  final String taskId;

  const SupervisorChatSheet({
    super.key,
    required this.taskId,
  });

  static void show(BuildContext context, String taskId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => SupervisorChatSheet(taskId: taskId),
    );
  }

  @override
  ConsumerState<SupervisorChatSheet> createState() => _SupervisorChatSheetState();
}

class _SupervisorChatSheetState extends ConsumerState<SupervisorChatSheet> {
  final TextEditingController _controller = TextEditingController();

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(supervisorProvider.notifier).setActiveTask(widget.taskId);
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _controller.text.trim();
    if (text.isNotEmpty) {
      _controller.clear();
      ref.read(supervisorProvider.notifier).sendMessage(text);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(supervisorProvider);

    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.4,
      maxChildSize: 0.95,
      builder: (context, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: const Color(0xFF141416),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            border: Border.all(color: Colors.white12),
          ),
          child: Column(
            children: [
              // Header
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: Colors.white10)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.psychology_outlined, color: Colors.cyanAccent, size: 22),
                    const SizedBox(width: 10),
                    const Text(
                      'Supervisor Assistant',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: Icon(
                        state.isPaused ? Icons.play_arrow : Icons.pause,
                        color: state.isPaused ? Colors.greenAccent : Colors.orangeAccent,
                      ),
                      onPressed: () {
                        if (state.isPaused) {
                          ref.read(supervisorProvider.notifier).sendSignal('resume');
                        } else {
                          ref.read(supervisorProvider.notifier).sendSignal('pause');
                        }
                      },
                      tooltip: state.isPaused ? 'Resume Main Worker' : 'Pause Main Worker',
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white70),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),

              // Messages list
              Expanded(
                child: state.messages.isEmpty
                    ? Center(
                        child: Text(
                          'Ask the Supervisor anything about the running task\ne.g., "Why is it editing this file?" or "Pause and show plan"',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
                        ),
                      )
                    : ListView.builder(
                        controller: scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: state.messages.length,
                        itemBuilder: (context, index) {
                          final msg = state.messages[index];
                          final isUser = msg.sender == 'user';
                          return Align(
                            alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                            child: Container(
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(12),
                              constraints: const BoxConstraints(maxWidth: 300),
                              decoration: BoxDecoration(
                                color: isUser ? const Color(0xFF2563EB) : const Color(0xFF22242B),
                                borderRadius: BorderRadius.circular(12),
                                border: isUser ? null : Border.all(color: Colors.white10),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    msg.content,
                                    style: const TextStyle(color: Colors.white, fontSize: 14),
                                  ),
                                  if (msg.tier == 'tier2') ...[
                                    const SizedBox(height: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: Colors.cyan.withOpacity(0.2),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: const Text(
                                        'Deep Reasoning',
                                        style: TextStyle(color: Colors.cyanAccent, fontSize: 10),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          );
                        },
                      ),
              ),

              if (state.isLoading)
                const Padding(
                  padding: EdgeInsets.all(8.0),
                  child: LinearProgressIndicator(backgroundColor: Colors.transparent),
                ),

              // Input bar
              Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: const TextStyle(color: Colors.white, fontSize: 14),
                        decoration: InputDecoration(
                          hintText: 'Message Supervisor...',
                          hintStyle: const TextStyle(color: Colors.white38),
                          filled: true,
                          fillColor: const Color(0xFF1C1D22),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(24),
                            borderSide: const BorderSide(color: Colors.white12),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(24),
                            borderSide: const BorderSide(color: Colors.white12),
                          ),
                        ),
                        onSubmitted: (_) => _submit(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      icon: const Icon(Icons.send_rounded, color: Colors.cyanAccent),
                      onPressed: _submit,
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
