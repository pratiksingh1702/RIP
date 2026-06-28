import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/chat_provider.dart';
import '../providers/project_provider.dart';
import '../providers/connection_provider.dart';
import '../widgets/chat/chat_bubble.dart';
import '../widgets/chat/typing_indicator.dart';
import '../widgets/common/error_banner.dart';
import '../widgets/overlays/command_palette.dart';
import '../widgets/overlays/project_switcher.dart';
import '../widgets/sidebar/app_drawer.dart';
import 'package:go_router/go_router.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  bool _isTyping = false;
  bool _showCommandPalette = false;
  bool _showProjectSwitcher = false;

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _textController.clear();
    await ref.read(chatProvider.notifier).addUserMessage(text);

    setState(() {
      _isTyping = true;
    });

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

    try {
      await Future.delayed(const Duration(seconds: 1));
      await ref.read(chatProvider.notifier).addRipMessage(
            'This is a sample response. The full RIP integration is coming soon!',
          );
    } catch (e) {
      await ref.read(chatProvider.notifier).addRipMessage(
            'Error: $e',
          );
    } finally {
      setState(() {
        _isTyping = false;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(chatProvider);
    final activeProject = ref.watch(activeProjectProvider);
    final connectionStatus = ref.watch(connectionStatusProvider);

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        title: const Text('RIP Chat'),
        actions: [
          activeProject.when(
            data: (project) => project != null
                ? Padding(
                    padding: const EdgeInsets.only(right: 16),
                    child: Chip(
                      label: Text(project.projectName),
                      avatar: const Icon(Icons.folder),
                    ),
                  )
                : const SizedBox.shrink(),
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => context.go('/setup'),
          ),
        ],
      ),
      body: Stack(
        children: [
          Column(
            children: [
              connectionStatus.when(
                data: (isConnected) {
                  if (!isConnected) {
                    return Padding(
                      padding: const EdgeInsets.all(8),
                      child: ErrorBanner(
                        message: 'Not connected to server',
                        onRetry: () => ref.invalidate(connectionStatusProvider),
                      ),
                    );
                  }
                  return const SizedBox.shrink();
                },
                loading: () => const SizedBox.shrink(),
                error: (error, _) => Padding(
                  padding: const EdgeInsets.all(8),
                  child: ErrorBanner(message: 'Connection error: $error'),
                ),
              ),
              Expanded(
                child: messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.chat_bubble_outline,
                              size: 80,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withValues(alpha: 0.3),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'Start a conversation with RIP',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurface
                                        .withOpacity(0.6),
                                  ),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        itemCount: messages.length + (_isTyping ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index == messages.length && _isTyping) {
                            return const TypingIndicator();
                          }
                          return ChatBubble(message: messages[index]);
                        },
                      ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _textController,
                          decoration: InputDecoration(
                            hintText: 'Ask RIP anything...',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(24),
                            ),
                            filled: true,
                          ),
                          onChanged: (value) {
                            if (value.startsWith('/') && !_showCommandPalette) {
                              setState(() {
                                _showCommandPalette = true;
                              });
                            } else if (value.startsWith('@') &&
                                !_showProjectSwitcher) {
                              setState(() {
                                _showProjectSwitcher = true;
                              });
                            } else if (!value.startsWith('/') &&
                                _showCommandPalette) {
                              setState(() {
                                _showCommandPalette = false;
                              });
                            } else if (!value.startsWith('@') &&
                                _showProjectSwitcher) {
                              setState(() {
                                _showProjectSwitcher = false;
                              });
                            }
                          },
                          onSubmitted: (_) => _sendMessage(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filled(
                        onPressed: _sendMessage,
                        icon: const Icon(Icons.send),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          if (_showCommandPalette)
            Container(
              color: Colors.black54,
              child: CommandPalette(
                onCommandSubmitted: (cmd) {
                  _textController.text = cmd;
                  _sendMessage();
                },
                onDismissed: () {
                  setState(() {
                    _showCommandPalette = false;
                  });
                },
              ),
            ),
          if (_showProjectSwitcher)
            Container(
              color: Colors.black54,
              child: ProjectSwitcher(
                onProjectSelected: (project) async {
                  await ref
                      .read(activeProjectNotifierProvider.notifier)
                      .setActiveProject(project.projectId);
                },
                onDismissed: () {
                  setState(() {
                    _showProjectSwitcher = false;
                  });
                },
              ),
            ),
        ],
      ),
    );
  }
}
