import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:rip_app/presentation/providers/llm_config_provider.dart';

import '../../core/design/app_colors.dart';
import '../../core/design/app_theme.dart';
import '../../data/models/message.dart';
import '../../data/models/project.dart';
import '../../utils/date_formatter.dart';
import '../providers/chat_provider.dart';
import '../providers/connection_provider.dart';
import '../providers/project_provider.dart';
import '../providers/chat_session_provider.dart';
import '../widgets/chat/chat_bubble.dart';
import '../widgets/common/error_banner.dart';
import '../widgets/sidebar/app_drawer.dart';
import '../../utils/command_parser.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  final _focusNode = FocusNode();
  bool _composerExpanded = false;
  bool _showScrollToBottom = false;
  double _headerT = 0;

  @override
  void initState() {
    super.initState();
    _textController.addListener(_handleComposerTextChanged);
    _focusNode.addListener(() => setState(() {}));
    _scrollController.addListener(_handleScroll);
  }

  @override
  void dispose() {
    _textController
      ..removeListener(_handleComposerTextChanged)
      ..dispose();
    _focusNode.dispose();
    _scrollController
      ..removeListener(_handleScroll)
      ..dispose();
    super.dispose();
  }

  void _handleComposerTextChanged() {
    final text = _textController.text.trimLeft();
    final shouldExpand = text.startsWith('/') || text.startsWith('@');
    if (text.startsWith('@') && !_composerExpanded) {
      ref.invalidate(projectListProvider);
    }
    if (shouldExpand != _composerExpanded) {
      setState(() => _composerExpanded = shouldExpand);
    } else if (shouldExpand) {
      setState(() {});
    }
  }

  void _handleScroll() {
    if (!_scrollController.hasClients) return;
    final offset = _scrollController.offset;
    final nextHeaderT = (offset / 120).clamp(0.0, 1.0);
    final distanceFromBottom =
        _scrollController.position.maxScrollExtent - offset;
    final nextShowScrollToBottom = distanceFromBottom > 260;
    if ((nextHeaderT - _headerT).abs() > 0.02 ||
        nextShowScrollToBottom != _showScrollToBottom) {
      setState(() {
        _headerT = nextHeaderT;
        _showScrollToBottom = nextShowScrollToBottom;
      });
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 340),
        curve: Curves.easeOutCubic,
      );
    }
  }

  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;
    if (text == '/workflow') {
      await _pickWorkflowForComposer();
      return;
    }

    HapticFeedback.lightImpact();
    _textController.clear();
    setState(() => _composerExpanded = false);

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    await ref.read(chatProvider.notifier).sendMessage(text);
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
  }

  Future<void> _pickWorkflowForComposer() async {
    HapticFeedback.selectionClick();
    final projectId = ref.read(activeProjectIdProvider);
    final selected = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      showDragHandle: true,
      builder: (context) => FutureBuilder<List<dynamic>>(
        future: ref.read(ripClientProvider).gatewayWorkflows(projectId: projectId),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const SizedBox(
              height: 220,
              child: Center(child: CircularProgressIndicator()),
            );
          }
          if (snapshot.hasError) {
            return _WorkflowPickerMessage(
              icon: Icons.error_outline_rounded,
              title: 'Could not load workflows',
              message: '${snapshot.error}',
            );
          }
          final workflows = (snapshot.data ?? const [])
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .where((item) => _workflowId(item).isNotEmpty)
              .toList();
          if (workflows.isEmpty) {
            return const _WorkflowPickerMessage(
              icon: Icons.account_tree_outlined,
              title: 'No workflows yet',
              message: 'Create a workflow in the canvas, then attach it here with /workflow.',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(14, 4, 14, 18),
            itemCount: workflows.length + 1,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              if (index == 0) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('Attach workflow', style: Theme.of(context).textTheme.titleMedium),
                );
              }
              final workflow = workflows[index - 1];
              final id = _workflowId(workflow);
              final blocks = workflow['blocks'] as List? ?? const [];
              final wires = workflow['wires'] as List? ?? const [];
              return ListTile(
                leading: const Icon(Icons.account_tree_rounded),
                title: Text('${workflow['name'] ?? 'Workflow'}', overflow: TextOverflow.ellipsis),
                subtitle: Text('${workflow['status'] ?? 'draft'} - ${blocks.length} blocks - ${wires.length} wires'),
                trailing: const Icon(Icons.add_link_rounded),
                onTap: () {
                  workflow['draft_id'] = id;
                  Navigator.pop(context, workflow);
                },
              );
            },
          );
        },
      ),
    );
    if (selected == null) return;
    if (!mounted) return;
    final id = _workflowId(selected);
    if (id.isEmpty) return;
    _textController.text = '/workflow $id ';
    _textController.selection = TextSelection.collapsed(offset: _textController.text.length);
    setState(() => _composerExpanded = false);
    _focusNode.requestFocus();
  }

  void _insertCommand(String command) {
    HapticFeedback.selectionClick();
    if (command == '/workflow') {
      _textController.clear();
      setState(() => _composerExpanded = false);
      _pickWorkflowForComposer();
      return;
    }
    final next = command.contains('<') ? command : '$command ';
    final start = next.indexOf('<');
    final end = next.indexOf('>');
    _textController.text = next;
    if (start >= 0 && end > start) {
      _textController.selection = TextSelection(baseOffset: start, extentOffset: end + 1);
    } else {
      _textController.selection = TextSelection.collapsed(offset: next.length);
    }
    setState(() => _composerExpanded = true);
    _focusNode.requestFocus();
  }

  Future<void> _selectProject(String projectId) async {
    HapticFeedback.selectionClick();
    await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(projectId);
    _textController.clear();
    setState(() => _composerExpanded = false);
    _focusNode.requestFocus();
  }

  Future<void> _createNewChat() async {
    HapticFeedback.selectionClick();
    final activeProjectId = ref.read(activeProjectIdProvider);
    await ref.read(chatSessionNotifierProvider.notifier).createNewChat(
          projectId: activeProjectId,
        );
    _textController.clear();
    setState(() => _composerExpanded = false);
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(chatProvider);
    final activeProject = ref.watch(activeProjectProvider);
    final connectionStatus = ref.watch(connectionStatusProvider);
    final isAssistantBusy = ref.watch(isAssistantBusyProvider);
    final activeSessionId = ref.watch(activeChatSessionIdProvider);

    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(),
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      body: Builder(
        builder: (context) {
          return Stack(
            children: [
              ColoredBox(color: Theme.of(context).scaffoldBackgroundColor),
              Column(
                children: [
                  Expanded(
                    child: activeProject.when(
                      loading: () => messages.isEmpty
                          ? const _PremiumEmptyState(project: null)
                          : _MessageList(
                              messages: messages,
                              project: null,
                              scrollController: _scrollController,
                            ),
                      error: (_, __) => messages.isEmpty
                          ? const _PremiumEmptyState(project: null)
                          : _MessageList(
                              messages: messages,
                              project: null,
                              scrollController: _scrollController,
                            ),
                      data: (project) => messages.isEmpty
                          ? _PremiumEmptyState(project: project)
                          : _MessageList(
                              messages: messages,
                              project: project,
                              scrollController: _scrollController,
                            ),
                    ),
                  ),
                ],
              ),
              _FloatingHeader(
                progress: _headerT,
                onMenuTap: () {
                  HapticFeedback.selectionClick();
                  Scaffold.of(context).openDrawer();
                },
                onSettingsTap: () {
                  HapticFeedback.selectionClick();
                  context.push('/setup');
                },
                onNewChatTap: _createNewChat,
                project: activeProject.maybeWhen(
                  data: (project) => project,
                  orElse: () => null,
                ),
                activeSessionId: activeSessionId,
              ),
              connectionStatus.when(
                data: (isConnected) => isConnected
                    ? const SizedBox.shrink()
                    : Positioned(
                        left: 16,
                        right: 16,
                        top: MediaQuery.paddingOf(context).top + 76,
                        child: ErrorBanner(
                          message: 'Not connected to server',
                          onRetry: () => ref.invalidate(connectionStatusProvider),
                        ),
                      ),
                loading: () => const SizedBox.shrink(),
                error: (error, _) => Positioned(
                  left: 16,
                  right: 16,
                  top: MediaQuery.paddingOf(context).top + 76,
                  child: ErrorBanner(message: 'Connection error: $error'),
                ),
              ),
              Positioned(
                right: 18,
                bottom: MediaQuery.paddingOf(context).bottom + 116,
                child: AnimatedScale(
                  scale: _showScrollToBottom ? 1 : 0,
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOutCubic,
                  child: _GlassIconButton(
                    icon: Icons.keyboard_arrow_down_rounded,
                    tooltip: 'Latest',
                    onPressed: _scrollToBottom,
                  ),
                ),
              ),
              const _BottomComposerFade(),
              Align(
                alignment: Alignment.bottomCenter,
                child: _FloatingComposer(
                  controller: _textController,
                  focusNode: _focusNode,
                  expanded: _composerExpanded,
                  isBusy: isAssistantBusy,
                  activeProjectName: activeProject.maybeWhen(
                    data: (project) => project?.projectName,
                    orElse: () => null,
                  ),
                  onSend: _sendMessage,
                  onStop: () {
                    HapticFeedback.mediumImpact();
                    ref.read(chatProvider.notifier).cancelCurrentRequest();
                  },
                  onCommandSelected: _insertCommand,
                  onProjectSelected: _selectProject,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

String _workflowId(Map<String, dynamic> workflow) {
  return workflow['draft_id']?.toString() ??
      workflow['workflow_id']?.toString() ??
      workflow['id']?.toString() ??
      '';
}

class _WorkflowPickerMessage extends StatelessWidget {
  const _WorkflowPickerMessage({
    required this.icon,
    required this.title,
    required this.message,
  });

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 250,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 34, color: colorScheme.primary),
            const SizedBox(height: 12),
            Text(title, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({
    required this.messages,
    required this.project,
    required this.scrollController,
  });

  final List<Message> messages;
  final Project? project;
  final ScrollController scrollController;

  @override
  Widget build(BuildContext context) {
    final itemCount = messages.length + (project == null ? 0 : 1);
    return ListView.builder(
      controller: scrollController,
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: const EdgeInsets.fromLTRB(0, 108, 0, 184),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        if (project != null && index == 0) {
          return _ProjectContextCard(project: project!);
        }
        final messageIndex = project == null ? index : index - 1;
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: Duration(milliseconds: 220 + (messageIndex % 4) * 34),
          curve: Curves.easeOutCubic,
          builder: (context, value, child) {
            return Opacity(
              opacity: value,
              child: Transform.translate(
                offset: Offset(0, 14 * (1 - value)),
                child: child,
              ),
            );
          },
          child: ChatBubble(
            message: messages[messageIndex],
            project: project,
          ),
        );
      },
    );
  }
}

class _ProjectContextCard extends StatelessWidget {
  const _ProjectContextCard({required this.project});

  final Project project;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.surface.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.border),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.account_tree_rounded, color: AppColors.primary, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      project.projectName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _ProjectStatPill(label: 'Files', value: '${project.filesCount}'),
                  _ProjectStatPill(label: 'Entities', value: '${project.entitiesCount}'),
                  _ProjectStatPill(label: 'Language', value: _primaryLanguage(project)),
                  _ProjectStatPill(label: 'Indexed', value: _indexedLabel(project)),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _primaryLanguage(Project project) {
    if (project.languages.isEmpty) return 'Unknown';
    return project.languages.take(2).join(', ');
  }

  String _indexedLabel(Project project) {
    final parsed = DateTime.tryParse(project.indexedAt);
    if (parsed == null) return project.indexedAt.isEmpty ? 'Unknown' : project.indexedAt;
    return DateFormatter.formatRelativeTime(parsed);
  }
}

class _ProjectStatPill extends StatelessWidget {
  const _ProjectStatPill({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.055),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.075)),
      ),
      child: Text(
        '$label: $value',
        style: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _FloatingHeader extends ConsumerWidget {
  const _FloatingHeader({
    required this.progress,
    required this.onMenuTap,
    required this.onSettingsTap,
    required this.onNewChatTap,
    required this.project,
    required this.activeSessionId,
  });

  final double progress;
  final VoidCallback onMenuTap;
  final VoidCallback onSettingsTap;
  final VoidCallback onNewChatTap;
  final Project? project;
  final String? activeSessionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chatSessionsAsync = ref.watch(chatSessionsProvider);
    final sessions = chatSessionsAsync.value ?? [];
    final activeSession = sessions.isNotEmpty 
        ? sessions.firstWhere(
            (s) => s.id == activeSessionId,
            orElse: () => sessions.first,
          )
        : null;

    final top = MediaQuery.paddingOf(context).top;
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    final height = lerpDouble(72, 60, progress)!;
    final veilAlpha = lerpDouble(0.74, 0.96, progress)!;
    final midFadeAlpha = lerpDouble(0.38, 0.66, progress)!;
    final tailFadeAlpha = lerpDouble(0.06, 0.18, progress)!;

    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: SizedBox(
        height: top + height + 28,
        child: Stack(
          children: [
            Positioned.fill(
              child: IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      stops: const [0, 0.48, 0.72, 0.90, 1],
                      colors: [
                        chrome.fadeColor.withValues(alpha: veilAlpha),
                        chrome.fadeColor
                            .withValues(alpha: veilAlpha * 0.96),
                        chrome.fadeColor.withValues(alpha: midFadeAlpha),
                        chrome.fadeColor.withValues(alpha: tailFadeAlpha),
                        chrome.fadeColor.withValues(alpha: 0),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
                child: SizedBox(
                  height: height,
                  child: Row(
                    children: [
                      _GlassIconButton(
                        icon: Icons.menu_rounded,
                        tooltip: 'Menu',
                        onPressed: onMenuTap,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            Text(
                              'RIP · Repository Intelligence',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 17,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            AnimatedSwitcher(
                              duration: const Duration(milliseconds: 180),
                              child: activeSession == null
                                  ? Text(
                                      'Start a new chat',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: TextStyle(
                                        color: AppColors.textSecondary,
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    )
                                  : Text(
                                      '${activeSession.title}${project != null ? ' · ' + project!.projectName : ''}',
                                      key: ValueKey(activeSession.id),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: TextStyle(
                                        color: AppColors.textSecondary
                                            .withValues(alpha: 0.78),
                                        fontSize: 11,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      _GlassIconButton(
                        icon: Icons.add_comment_rounded,
                        tooltip: 'New Chat',
                        onPressed: onNewChatTap,
                      ),
                      const SizedBox(width: 8),
                      _GlassIconButton(icon: Icons.dashboard_rounded, tooltip: 'Dashboard', onPressed: () => context.push('/workspace')),
                      const SizedBox(width: 8),
                      _GlassIconButton(
                        icon: Icons.tune_rounded,
                        tooltip: 'Settings',
                        onPressed: onSettingsTap,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BottomComposerFade extends StatelessWidget {
  const _BottomComposerFade();

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return Positioned(
      left: 0,
      right: 0,
      bottom: 0,
      height: bottom + chrome.bottomFadeHeight,
      child: IgnorePointer(
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              stops: const [0, 0.28, 0.58, 0.82, 1],
              colors: [
                chrome.fadeColor.withValues(alpha: 0),
                chrome.fadeColor.withValues(alpha: 0.16),
                chrome.fadeColor.withValues(alpha: 0.48),
                chrome.fadeColor.withValues(alpha: 0.78),
                chrome.fadeColor.withValues(alpha: 0.96),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FloatingComposer extends StatelessWidget {
  const _FloatingComposer({
    required this.controller,
    required this.focusNode,
    required this.expanded,
    required this.isBusy,
    required this.activeProjectName,
    required this.onSend,
    required this.onStop,
    required this.onCommandSelected,
    required this.onProjectSelected,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool expanded;
  final bool isBusy;
  final String? activeProjectName;
  final VoidCallback onSend;
  final VoidCallback onStop;
  final ValueChanged<String> onCommandSelected;
  final ValueChanged<String> onProjectSelected;

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    final hasFocus = focusNode.hasFocus;
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    final radius = expanded ? chrome.composerExpandedRadius : chrome.composerRadius;

    return Padding(
      padding: EdgeInsets.fromLTRB(18, 0, 18, bottom + 30),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(radius),
          border: Border.all(
            color: hasFocus
                ? chrome.focusBorderColor.withValues(alpha: 0.56)
                : chrome.borderColor.withValues(alpha: 0.82),
          ),
          boxShadow: [
            BoxShadow(
              color: chrome.shadowColor.withValues(alpha: 0.42),
              blurRadius: 36,
              offset: const Offset(0, 20),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(radius),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: chrome.composerSurface.withValues(alpha: 0.98),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 9, 12, 9),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                    AnimatedSize(
                      duration: const Duration(milliseconds: 220),
                      curve: Curves.easeOutCubic,
                      child: isBusy
                          ? Padding(
                              padding: const EdgeInsets.fromLTRB(4, 2, 4, 10),
                              child: _ComposerLoadingBar(onStop: onStop),
                            )
                          : const SizedBox.shrink(),
                    ),
                    AnimatedSize(
                      duration: const Duration(milliseconds: 260),
                      curve: Curves.easeOutCubic,
                      alignment: Alignment.topCenter,
                      child: expanded
                          ? Padding(
                              padding: const EdgeInsets.fromLTRB(4, 4, 4, 10),
                              child: _ComposerSuggestions(
                                controller: controller,
                                onCommandSelected: onCommandSelected,
                                onProjectSelected: onProjectSelected,
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        _ComposerButton(
                          label: '@',
                          tooltip: 'Projects',
                          onPressed: () {
                            controller.text = '@';
                            controller.selection = TextSelection.collapsed(
                              offset: controller.text.length,
                            );
                            focusNode.requestFocus();
                          },
                        ),
                        Expanded(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxHeight: 136),
                            child: TextField(
                              controller: controller,
                              focusNode: focusNode,
                              cursorColor: AppColors.primary,
                              minLines: 1,
                              maxLines: 6,
                              textInputAction: TextInputAction.newline,
                              keyboardType: TextInputType.multiline,
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 15,
                                height: 1.35,
                              ),
                              decoration: InputDecoration(
                                hintText: activeProjectName == null
                                    ? 'Select a repository, then query architecture'
                                    : 'Explore ${activeProjectName!}',
                                hintStyle: TextStyle(
                                  color: AppColors.textSecondary
                                      .withValues(alpha: 0.72),
                                  fontSize: 15,
                                ),
                                filled: false,
                                isDense: true,
                                border: InputBorder.none,
                                enabledBorder: InputBorder.none,
                                focusedBorder: InputBorder.none,
                                contentPadding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 12,
                                ),
                              ),
                              onSubmitted: (_) => onSend(),
                            ),
                          ),
                        ),
                        _ComposerButton(
                          label: '/',
                          tooltip: 'Commands',
                          onPressed: () {
                            controller.text = '/';
                            controller.selection = TextSelection.collapsed(
                              offset: controller.text.length,
                            );
                            focusNode.requestFocus();
                          },
                        ),
                        const SizedBox(width: 4),
                        isBusy
                            ? _StopSendButton(onPressed: onStop)
                            : _SendButton(onPressed: onSend),
                      ],
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ComposerLoadingBar extends StatelessWidget {
  const _ComposerLoadingBar({required this.onStop});

  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return ClipRRect(
      borderRadius: BorderRadius.circular(18),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: chrome.suggestionSurface.withValues(alpha: 0.42),
          border: Border.all(color: chrome.borderColor.withValues(alpha: 0.76)),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const LinearProgressIndicator(
              minHeight: 2,
              color: AppColors.primary,
              backgroundColor: Colors.transparent,
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
              child: Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      'Querying repository graph. Deep analysis can take a while.',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppColors.textSecondary.withValues(alpha: 0.88),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Tooltip(
                    message: 'Stop request',
                    child: IconButton(
                      onPressed: onStop,
                      icon: const Icon(Icons.stop_rounded),
                      color: AppColors.error,
                      iconSize: 18,
                      style: IconButton.styleFrom(
                        fixedSize: const Size(32, 32),
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        backgroundColor: chrome.controlSurface,
                        shape: const CircleBorder(),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  const _SendButton({required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onPressed,
        child: Ink(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.primary,
            boxShadow: [
              BoxShadow(
                color: AppColors.primary.withValues(alpha: 0.32),
                blurRadius: 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: const Icon(
            Icons.arrow_upward_rounded,
            color: Colors.white,
            size: 22,
          ),
        ),
      ),
    );
  }
}

class _StopSendButton extends StatelessWidget {
  const _StopSendButton({required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onPressed,
        child: Ink(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.error.withValues(alpha: 0.16),
            border: Border.all(color: AppColors.error.withValues(alpha: 0.38)),
          ),
          child: const Icon(
            Icons.stop_rounded,
            color: AppColors.error,
            size: 22,
          ),
        ),
      ),
    );
  }
}

class _ComposerButton extends StatelessWidget {
  const _ComposerButton({
    required this.label,
    required this.tooltip,
    required this.onPressed,
  });

  final String label;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return Tooltip(
      message: tooltip,
      child: IconButton(
        onPressed: () {
          HapticFeedback.selectionClick();
          onPressed();
        },
        icon: Text(
          label,
          style: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w900,
          ),
        ),
        style: IconButton.styleFrom(
          fixedSize: const Size(42, 42),
          backgroundColor: chrome.controlSurface,
          shape: const CircleBorder(),
        ),
      ),
    );
  }
}

class _ComposerSuggestions extends ConsumerWidget {
  const _ComposerSuggestions({
    required this.controller,
    required this.onCommandSelected,
    required this.onProjectSelected,
  });

  final TextEditingController controller;
  final ValueChanged<String> onCommandSelected;
  final ValueChanged<String> onProjectSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = controller.text.trimLeft();
    if (text.startsWith('@')) {
      final filter = text.substring(1).toLowerCase();
      final projectsAsync = ref.watch(projectListProvider);
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _SuggestionHeader(
            title: 'Projects',
            onRefresh: () {
              HapticFeedback.selectionClick();
              ref.invalidate(projectListProvider);
            },
          ),
          const SizedBox(height: 8),
          projectsAsync.when(
            loading: () => const SizedBox(
              height: 44,
              child: Center(
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),
            error: (error, _) => Text(
              'Projects unavailable',
              style: TextStyle(
                color: AppColors.textSecondary.withValues(alpha: 0.78),
              ),
            ),
            data: (projects) {
              final filtered = projects
                  .where((project) =>
                      project.projectName.toLowerCase().contains(filter) ||
                      project.locationLabel.toLowerCase().contains(filter) ||
                      (project.repositoryOwner
                              ?.toLowerCase()
                              .contains(filter) ??
                          false) ||
                      (project.branch?.toLowerCase().contains(filter) ??
                          false))
                  .take(5)
                  .toList();
              return _SuggestionList(
                emptyText: 'No projects found',
                children: [
                  for (final project in filtered)
                    _SuggestionRow(
                      icon: Icons.folder_open_rounded,
                      title: project.projectName,
                      subtitle: _projectMetadataLine(project),
                      onTap: () => onProjectSelected(project.projectId),
                    ),
                ],
              );
            },
          ),
        ],
      );
    }

    final slashBody = text.startsWith('/') ? text.substring(1) : '';
    final commandToken = slashBody.split(RegExp(r'\s+')).first.toLowerCase();
    final filter = slashBody.contains(RegExp(r'\s')) ? commandToken : slashBody.toLowerCase();
    final commands = CommandParser.getAvailableCommands()
        .where((command) =>
            command['name'].toString().toLowerCase().contains(filter) ||
            command['description'].toString().toLowerCase().contains(filter))
        .toList();
    Map<String, dynamic>? matchedCommand;
    for (final command in CommandParser.getAvailableCommands()) {
      if (_commandName(command) == commandToken) {
        matchedCommand = command;
        break;
      }
    }
    final flags = (matchedCommand?['flags'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _SuggestionList(
          emptyText: 'No commands found',
          children: [
            for (final command in commands)
              _SuggestionRow(
                icon: Icons.terminal_rounded,
                title: command['name'],
                subtitle: command['description'],
                onTap: () => onCommandSelected(command['name'].toString()),
              ),
          ],
        ),
        if (flags.isNotEmpty) ...[
          const SizedBox(height: 10),
          _FlagChips(
            flags: flags,
            onSelected: _insertFlag,
          ),
                  if (commandToken == 'agent') ...[
          const SizedBox(height: 10),
          _LLMConfigChips(),
        ],
        ],
      ],
    );
  }

  String _commandName(Map<String, dynamic> command) {
    return command['name'].toString().split(' ').first.replaceFirst('/', '').toLowerCase();
  }

  void _insertFlag(Map<String, dynamic> flag) {
    HapticFeedback.selectionClick();
    final name = flag['name'].toString();
    final current = controller.text;
    final next = current.endsWith(' ') ? '$current$name ' : '$current $name ';
    controller.value = TextEditingValue(
      text: next,
      selection: TextSelection.collapsed(offset: next.length),
    );
  }

  String _projectMetadataLine(project) {
    final parts = <String>[
      if (project.repositoryOwner != null) 'Owner: ${project.repositoryOwner}',
      if (project.branch != null && project.branch!.trim().isNotEmpty)
        'Branch: ${project.branch}',
      '${project.filesCount} files',
      project.locationLabel,
    ];
    return parts.join('  |  ');
  }
}

class _FlagChips extends StatelessWidget {
  const _FlagChips({
    required this.flags,
    required this.onSelected,
  });

  final List<Map<String, dynamic>> flags;
  final ValueChanged<Map<String, dynamic>> onSelected;

  @override
  Widget build(BuildContext context) {
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return Align(
      alignment: Alignment.centerLeft,
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final flag in flags)
            Tooltip(
              message: flag['description'].toString(),
              child: InkWell(
                borderRadius: BorderRadius.circular(18),
                onTap: () => onSelected(flag),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                  decoration: BoxDecoration(
                    color: chrome.suggestionSurface.withValues(alpha: 0.72),
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color: chrome.borderColor.withValues(alpha: 0.82),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        flag['name'].toString(),
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      if (flag['value'] != null) ...[
                        const SizedBox(width: 5),
                        Text(
                          flag['value'].toString(),
                          style: TextStyle(
                            color: AppColors.textSecondary.withValues(alpha: 0.75),
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SuggestionHeader extends StatelessWidget {
  const _SuggestionHeader({
    required this.title,
    required this.onRefresh,
  });

  final String title;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return Row(
      children: [
        Text(
          title,
          style: TextStyle(
            color: AppColors.textSecondary.withValues(alpha: 0.82),
            fontSize: 12,
            fontWeight: FontWeight.w800,
          ),
        ),
        const Spacer(),
        Tooltip(
          message: 'Reload projects',
          child: IconButton(
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh_rounded, size: 18),
            color: AppColors.textSecondary,
            style: IconButton.styleFrom(
              fixedSize: const Size(32, 32),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              backgroundColor: chrome.controlSurface,
              shape: const CircleBorder(),
            ),
          ),
        ),
      ],
    );
  }
}

class _SuggestionList extends StatelessWidget {
  const _SuggestionList({required this.children, required this.emptyText});

  final List<Widget> children;
  final String emptyText;

  @override
  Widget build(BuildContext context) {
    if (children.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Text(
          emptyText,
          style: TextStyle(color: AppColors.textSecondary.withValues(alpha: 0.78)),
        ),
      );
    }
    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 210),
      child: ListView.separated(
        padding: EdgeInsets.zero,
        shrinkWrap: true,
        itemCount: children.length,
        separatorBuilder: (_, __) => const SizedBox(height: 7),
        itemBuilder: (context, index) => children[index],
      ),
    );
  }
}

class _SuggestionRow extends StatelessWidget {
  const _SuggestionRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return Material(
      color: chrome.suggestionSurface.withValues(alpha: 0.54),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(icon, size: 18, color: AppColors.textSecondary),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppColors.textSecondary.withValues(alpha: 0.72),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PremiumEmptyState extends StatelessWidget {
  const _PremiumEmptyState({required this.project});

  final Project? project;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(28, 104, 28, 172),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 92,
              height: 92,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: colorScheme.surfaceContainerHighest,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.28),
                    blurRadius: 46,
                    offset: const Offset(0, 18),
                  ),
                ],
              ),
              child: const Icon(
                Icons.account_tree_rounded,
                color: Colors.white,
                size: 42,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              project == null
                  ? 'Select a repository to inspect'
                  : project!.projectName,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 25,
                height: 1.12,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              project == null
                  ? 'RIP indexes repositories into a graph so you can trace architecture, dependencies, workflows, and symbols.'
                  : '${project!.filesCount} files · ${project!.entitiesCount} entities · ${_primaryLanguage(project!)} · indexed ${_indexedLabel(project!)}',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: colorScheme.onSurfaceVariant.withValues(alpha: 0.9),
                fontSize: 14,
                height: 1.45,
              ),
            ),
            const SizedBox(height: 18),
            if (project != null)
              _ProjectContextCard(project: project!)
            else
              Text(
                'Use @ or the drawer to select an indexed codebase.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: colorScheme.onSurfaceVariant.withValues(alpha: 0.74),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _primaryLanguage(Project project) {
    if (project.languages.isEmpty) return 'unknown language';
    return project.languages.take(2).join(', ');
  }

  String _indexedLabel(Project project) {
    final parsed = DateTime.tryParse(project.indexedAt);
    if (parsed == null) return project.indexedAt.isEmpty ? 'unknown' : project.indexedAt;
    return DateFormatter.formatRelativeTime(parsed);
  }
}
class _LLMConfigChips extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final llmConfigsAsync = ref.watch(llmConfigsProvider);
    return llmConfigsAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (configs) {
        if (configs.isEmpty) return const SizedBox.shrink();
        final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
            const ChatChromeTheme.dark();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'LLM Configs',
              style: TextStyle(
                color: AppColors.textSecondary.withValues(alpha: 0.82),
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final config in configs)
                  Tooltip(
                    message: '${config['provider']} / ${config['model']}',
                    child: InkWell(
                      borderRadius: BorderRadius.circular(18),
                      onTap: () {
                        HapticFeedback.selectionClick();
                        final text = '/agent --model ${config['id']} ';
                        // Use the controller to update text
                        final controller = (context as Element).findAncestorWidgetOfExactType<_FloatingComposer>()?.controller;
                        if (controller != null) {
                          controller.text = text;
                          controller.selection = TextSelection.collapsed(offset: text.length);
                        }
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                        decoration: BoxDecoration(
                          color: chrome.suggestionSurface.withValues(alpha: 0.72),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(
                            color: chrome.borderColor.withValues(alpha: 0.82),
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              config['has_api_key'] == true ? Icons.vpn_key_rounded : Icons.cloud_outlined,
                              size: 14,
                              color: AppColors.textSecondary,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              '${config['provider']}: ${config['model']}',
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        );
      },
    );
  }
}

class _GlassIconButton extends StatelessWidget {
  const _GlassIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final chrome = Theme.of(context).extension<ChatChromeTheme>() ??
        const ChatChromeTheme.dark();
    return Tooltip(
      message: tooltip,
      child: ClipOval(
        child: Material(
          color: chrome.controlSurface,
          shape: CircleBorder(
            side: BorderSide(color: chrome.borderColor.withValues(alpha: 0.82)),
          ),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: onPressed,
            child: SizedBox(
              width: 44,
              height: 44,
              child: Icon(icon, color: AppColors.textPrimary, size: 22),
            ),
          ),
        ),
      ),
    );
  }
}
