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
import '../providers/gateway_provider.dart';
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? Colors.black : Theme.of(context).scaffoldBackgroundColor;
    final messages = ref.watch(chatProvider);
    final activeProject = ref.watch(activeProjectProvider);
    final connectionStatus = ref.watch(connectionStatusProvider);
    final isAssistantBusy = ref.watch(isAssistantBusyProvider);
    final activeSessionId = ref.watch(activeChatSessionIdProvider);

    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(),
      drawerEdgeDragWidth: MediaQuery.sizeOf(context).width * 0.4,
      backgroundColor: bgColor,
      body: Builder(
        builder: (context) {
          return GestureDetector(
            onHorizontalDragEnd: (details) {
              // Open drawer when swiping rightwards (positive velocity)
              if ((details.primaryVelocity ?? 0) > 250) {
                HapticFeedback.selectionClick();
                Scaffold.of(context).openDrawer();
              }
            },
            child: Stack(
              children: [
                ColoredBox(color: bgColor),
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
          ),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            decoration: BoxDecoration(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.06)
                  : Colors.black.withValues(alpha: 0.04),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.1)
                    : Colors.black.withValues(alpha: 0.08),
              ),
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
                          style: TextStyle(
                            color: isDark ? Colors.white : Colors.black87,
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.white.withValues(alpha: 0.08)
            : Colors.black.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.1)
              : Colors.black.withValues(alpha: 0.08),
        ),
      ),
      child: Text(
        '$label: $value',
        style: TextStyle(
          color: isDark ? Colors.white70 : Colors.black87,
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
    final top = MediaQuery.paddingOf(context).top;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final fadeColor = isDark ? Colors.black : Theme.of(context).scaffoldBackgroundColor;
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
                        fadeColor.withValues(alpha: veilAlpha),
                        fadeColor.withValues(alpha: veilAlpha * 0.96),
                        fadeColor.withValues(alpha: midFadeAlpha),
                        fadeColor.withValues(alpha: tailFadeAlpha),
                        fadeColor.withValues(alpha: 0),
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
                      const SizedBox(width: 8),
                      Expanded(
                        child: _HeaderDropdownSelector(project: project),
                      ),
                      const SizedBox(width: 8),
                      _GlassIconButton(
                        icon: Icons.add_comment_rounded,
                        tooltip: 'New Chat',
                        onPressed: onNewChatTap,
                      ),
                      const SizedBox(width: 8),
                      _GlassIconButton(
                        icon: Icons.dashboard_rounded,
                        tooltip: 'Dashboard',
                        onPressed: () => context.push('/workspace'),
                      ),
                      const SizedBox(width: 8),
                      _GlassIconButton(
                        icon: Icons.tune_rounded,
                        tooltip: 'Settings',
                        onPressed: onSettingsTap,
                      ),
                      const SizedBox(width: 8),
                      const _EffortSelectorButton(),
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

class _HeaderDropdownSelector extends ConsumerStatefulWidget {
  const _HeaderDropdownSelector({
    required this.project,
  });

  final Project? project;

  @override
  ConsumerState<_HeaderDropdownSelector> createState() =>
      __HeaderDropdownSelectorState();
}

class __HeaderDropdownSelectorState
    extends ConsumerState<_HeaderDropdownSelector> {
  bool _showProjectSelector = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onVerticalDragEnd: (details) {
        final dy = details.primaryVelocity ?? 0;
        if (dy < -100) {
          if (!_showProjectSelector) {
            HapticFeedback.mediumImpact();
            setState(() => _showProjectSelector = true);
          }
        } else if (dy > 100) {
          if (_showProjectSelector) {
            HapticFeedback.mediumImpact();
            setState(() => _showProjectSelector = false);
          }
        }
      },
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            margin: const EdgeInsets.symmetric(vertical: 2),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.08)
                  : Colors.black.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.12)
                    : Colors.black.withValues(alpha: 0.1),
                width: 1,
              ),
            ),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 240),
              transitionBuilder: (child, animation) {
                final slideAnimation = Tween<Offset>(
                  begin: const Offset(0, 0.2),
                  end: Offset.zero,
                ).animate(animation);
                return FadeTransition(
                  opacity: animation,
                  child: SlideTransition(position: slideAnimation, child: child),
                );
              },
              child: _showProjectSelector
                  ? _buildProjectDropdown(context)
                  : _buildLlmDropdown(context),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLlmDropdown(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final llmConfigsAsync = ref.watch(gatewayLlmConfigsProvider);
    final preferredConfigId = ref.watch(preferredLLMConfigProvider);
    final configs = llmConfigsAsync.value ?? [];

    Map<String, dynamic>? selectedConfig;
    if (preferredConfigId != null && configs.isNotEmpty) {
      try {
        selectedConfig = configs.firstWhere(
          (c) => c['id']?.toString() == preferredConfigId,
        );
      } catch (_) {
        selectedConfig = configs.first;
      }
    } else if (configs.isNotEmpty) {
      selectedConfig = configs.first;
    }

    final displayName = selectedConfig != null
        ? (selectedConfig['model']?.toString() ??
            selectedConfig['id']?.toString() ??
            'Select Model')
        : 'Select Model';

    return PopupMenuButton<String>(
      key: const ValueKey('llm_header_dropdown'),
      tooltip: 'Change LLM',
      offset: const Offset(0, 40),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isDark
              ? Colors.white.withValues(alpha: 0.15)
              : Colors.black.withValues(alpha: 0.1),
        ),
      ),
      color: isDark
          ? const Color(0xFF13132B).withValues(alpha: 0.96)
          : Colors.white.withValues(alpha: 0.96),
      elevation: 0,
      onSelected: (val) {
        HapticFeedback.selectionClick();
        if (val == '__manage__') {
          context.push('/llm-settings');
        } else {
          ref.read(preferredLLMConfigProvider.notifier).state = val;
        }
      },
      itemBuilder: (context) {
        final items = <PopupMenuEntry<String>>[];

        items.add(
          PopupMenuItem<String>(
            enabled: false,
            child: Row(
              children: [
                const Icon(Icons.psychology_rounded, size: 16, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(
                  'LLM Models',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: isDark ? Colors.white70 : Colors.black54,
                  ),
                ),
              ],
            ),
          ),
        );
        items.add(const PopupMenuDivider());

        if (configs.isEmpty) {
          items.add(
            PopupMenuItem<String>(
              enabled: false,
              child: Text(
                'No models loaded',
                style: TextStyle(
                  fontSize: 13,
                  color: isDark ? Colors.white70 : Colors.black87,
                ),
              ),
            ),
          );
        } else {
          for (final cfg in configs) {
            final id = cfg['id']?.toString() ?? '';
            final provider = cfg['provider']?.toString() ?? '';
            final model = cfg['model']?.toString() ?? id;
            final isSelected = (preferredConfigId == id) || (preferredConfigId == null && cfg == configs.first);

            items.add(
              PopupMenuItem<String>(
                value: id,
                child: Row(
                  children: [
                    Icon(
                      isSelected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                      size: 18,
                      color: isSelected ? AppColors.primary : (isDark ? Colors.white38 : Colors.black38),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            model,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              color: isDark ? Colors.white : Colors.black87,
                            ),
                          ),
                          if (provider.isNotEmpty)
                            Text(
                              provider,
                              style: TextStyle(
                                fontSize: 11,
                                color: isDark ? Colors.white54 : Colors.black54,
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

        items.add(const PopupMenuDivider());
        items.add(
          PopupMenuItem<String>(
            value: '__manage__',
            child: Row(
              children: [
                const Icon(Icons.tune_rounded, size: 18, color: AppColors.primary),
                const SizedBox(width: 10),
                Text(
                  'Manage LLM Settings',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: isDark ? Colors.white : Colors.black87,
                  ),
                ),
              ],
            ),
          ),
        );

        return items;
      },
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.psychology_rounded, size: 16, color: AppColors.primary),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              displayName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: isDark ? Colors.white : Colors.black87,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 4),
          Icon(
            Icons.keyboard_arrow_down_rounded,
            size: 18,
            color: isDark ? Colors.white60 : Colors.black54,
          ),
        ],
      ),
    );
  }

  Widget _buildProjectDropdown(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final projectsAsync = ref.watch(projectListProvider);
    final activeProjectId = ref.watch(activeProjectIdProvider);
    final projects = projectsAsync.value ?? [];

    final activeProject = widget.project;
    final displayName = activeProject?.projectName ?? 'Select Project';

    return PopupMenuButton<String>(
      key: const ValueKey('project_header_dropdown'),
      tooltip: 'Change Project',
      offset: const Offset(0, 40),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isDark
              ? Colors.white.withValues(alpha: 0.15)
              : Colors.black.withValues(alpha: 0.1),
        ),
      ),
      color: isDark
          ? const Color(0xFF13132B).withValues(alpha: 0.96)
          : Colors.white.withValues(alpha: 0.96),
      elevation: 0,
      onSelected: (val) async {
        HapticFeedback.selectionClick();
        await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(val);
      },
      itemBuilder: (context) {
        final items = <PopupMenuEntry<String>>[];

        items.add(
          PopupMenuItem<String>(
            enabled: false,
            child: Row(
              children: [
                const Icon(Icons.account_tree_rounded, size: 16, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(
                  'Projects',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: isDark ? Colors.white70 : Colors.black54,
                  ),
                ),
              ],
            ),
          ),
        );
        items.add(const PopupMenuDivider());

        if (projects.isEmpty) {
          items.add(
            PopupMenuItem<String>(
              enabled: false,
              child: Text(
                'No projects indexed',
                style: TextStyle(
                  fontSize: 13,
                  color: isDark ? Colors.white70 : Colors.black87,
                ),
              ),
            ),
          );
        } else {
          for (final p in projects) {
            final isSelected = p.projectId == activeProjectId;
            items.add(
              PopupMenuItem<String>(
                value: p.projectId,
                child: Row(
                  children: [
                    Icon(
                      isSelected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                      size: 18,
                      color: isSelected ? AppColors.primary : (isDark ? Colors.white38 : Colors.black38),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            p.projectName,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              color: isDark ? Colors.white : Colors.black87,
                            ),
                          ),
                          Text(
                            '${p.filesCount} files • ${p.entitiesCount} entities',
                            style: TextStyle(
                              fontSize: 11,
                              color: isDark ? Colors.white54 : Colors.black54,
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

        return items;
      },
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.account_tree_rounded, size: 16, color: AppColors.primary),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              displayName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: isDark ? Colors.white : Colors.black87,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 4),
          Icon(
            Icons.keyboard_arrow_down_rounded,
            size: 18,
            color: isDark ? Colors.white60 : Colors.black54,
          ),
        ],
      ),
    );
  }
}

class _BottomComposerFade extends StatelessWidget {
  const _BottomComposerFade();

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final fadeColor = isDark ? Colors.black : Theme.of(context).scaffoldBackgroundColor;

    return Positioned(
      left: 0,
      right: 0,
      bottom: 0,
      height: bottom + 110,
      child: IgnorePointer(
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              stops: const [0, 0.28, 0.58, 0.82, 1],
              colors: [
                fadeColor.withValues(alpha: 0),
                fadeColor.withValues(alpha: 0.16),
                fadeColor.withValues(alpha: 0.48),
                fadeColor.withValues(alpha: 0.78),
                fadeColor.withValues(alpha: 0.96),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FloatingComposer extends StatefulWidget {
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
  State<_FloatingComposer> createState() => _FloatingComposerState();
}

class _FloatingComposerState extends State<_FloatingComposer> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onTextChanged);
    super.dispose();
  }

  void _onTextChanged() {
    setState(() {});
  }

  void _acceptSuggestion(String suffix) {
    if (suffix.isEmpty) return;
    HapticFeedback.lightImpact();
    final newText = widget.controller.text + suffix;
    widget.controller.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(offset: newText.length),
    );
  }

  String _getInlineSuggestionSuffix(String input) {
    if (input.isEmpty) return '';
    final trimmed = input.trimLeft();

    if (trimmed.startsWith('/')) {
      final slashBody = trimmed.substring(1);
      if (slashBody.isEmpty) return 'agent --direct ';

      final commands = CommandParser.getAvailableCommands();
      for (final cmd in commands) {
        final nameWithArgs = cmd['name'].toString();
        final nameOnly = nameWithArgs.split(' ').first;
        final cmdName = nameOnly.replaceFirst('/', '').toLowerCase();

        if (cmdName.startsWith(slashBody.toLowerCase()) && cmdName.length > slashBody.length) {
          final remaining = cmdName.substring(slashBody.length);
          if (cmdName == 'agent') {
            return '$remaining --direct ';
          }
          return '$remaining ';
        } else if (cmdName == slashBody.toLowerCase()) {
          if (cmdName == 'agent' && !trimmed.contains('--direct')) {
            return ' --direct ';
          }
        }
      }
      return '';
    }

    final lower = trimmed.toLowerCase();
    const presets = [
      'explain system architecture',
      'show project dependencies',
      'trace query execution flow',
      'find dead code in codebase',
      'run autonomous agent task',
      'search function implementation',
    ];

    for (final preset in presets) {
      if (preset.startsWith(lower) && preset.length > lower.length) {
        return preset.substring(lower.length);
      }
    }

    return '';
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    final hasFocus = widget.focusNode.hasFocus;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final radius = widget.expanded ? 28.0 : 24.0;
    final suffix = _getInlineSuggestionSuffix(widget.controller.text);

    return Padding(
      padding: EdgeInsets.fromLTRB(18, 0, 18, bottom + 28),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(radius),
          boxShadow: [
            BoxShadow(
              color: isDark ? Colors.black45 : Colors.black12,
              blurRadius: 36,
              offset: const Offset(0, 20),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(radius),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 240),
              curve: Curves.easeOutCubic,
              decoration: BoxDecoration(
                color: isDark
                    ? const Color(0xFF13132B).withValues(alpha: 0.85)
                    : Colors.white.withValues(alpha: 0.85),
                borderRadius: BorderRadius.circular(radius),
                border: Border.all(
                  color: hasFocus
                      ? AppColors.primary
                      : (isDark
                          ? Colors.white.withValues(alpha: 0.12)
                          : Colors.black.withValues(alpha: 0.1)),
                  width: 1,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    AnimatedSize(
                      duration: const Duration(milliseconds: 200),
                      curve: Curves.easeOutCubic,
                      child: widget.isBusy
                          ? Padding(
                              padding: const EdgeInsets.fromLTRB(2, 2, 2, 8),
                              child: _ComposerLoadingBar(onStop: widget.onStop),
                            )
                          : const SizedBox.shrink(),
                    ),
                    AnimatedSize(
                      duration: const Duration(milliseconds: 240),
                      curve: Curves.easeOutCubic,
                      alignment: Alignment.topCenter,
                      child: widget.expanded
                          ? Padding(
                              padding: const EdgeInsets.fromLTRB(2, 2, 2, 8),
                              child: _ComposerSuggestions(
                                controller: widget.controller,
                                onCommandSelected: widget.onCommandSelected,
                                onProjectSelected: widget.onProjectSelected,
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    // Row 1: Active Project / Context Chip (Top Tag)
                    if (widget.activeProjectName != null) ...[
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: isDark
                                ? Colors.white.withValues(alpha: 0.08)
                                : Colors.black.withValues(alpha: 0.06),
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(
                              color: isDark
                                  ? Colors.white.withValues(alpha: 0.12)
                                  : Colors.black.withValues(alpha: 0.08),
                            ),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.account_tree_rounded, size: 13, color: AppColors.primary),
                              const SizedBox(width: 5),
                              Text(
                                widget.activeProjectName!,
                                style: TextStyle(
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.w600,
                                  color: isDark ? Colors.white70 : Colors.black87,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                    // Row 2: Text Input Field Area
                    GestureDetector(
                      onHorizontalDragEnd: (details) {
                        if (details.primaryVelocity != null && details.primaryVelocity! > 50) {
                          _acceptSuggestion(suffix);
                        }
                      },
                      child: Stack(
                        alignment: Alignment.centerLeft,
                        children: [
                          if (suffix.isNotEmpty && widget.controller.text.isNotEmpty)
                            IgnorePointer(
                              child: Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                                child: Text.rich(
                                  TextSpan(
                                    children: [
                                      TextSpan(
                                        text: widget.controller.text,
                                        style: const TextStyle(
                                          color: Colors.transparent,
                                          fontSize: 14.5,
                                          height: 1.35,
                                          fontWeight: FontWeight.w500,
                                        ),
                                      ),
                                      TextSpan(
                                        text: suffix,
                                        style: TextStyle(
                                          color: isDark ? Colors.white38 : Colors.black38,
                                          fontSize: 14.5,
                                          height: 1.35,
                                          fontWeight: FontWeight.w500,
                                          fontStyle: FontStyle.italic,
                                        ),
                                      ),
                                    ],
                                  ),
                                  maxLines: 4,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ),
                          ConstrainedBox(
                            constraints: const BoxConstraints(maxHeight: 120),
                            child: TextField(
                              controller: widget.controller,
                              focusNode: widget.focusNode,
                              cursorColor: AppColors.primary,
                              minLines: 1,
                              maxLines: 4,
                              textInputAction: TextInputAction.newline,
                              keyboardType: TextInputType.multiline,
                              style: TextStyle(
                                color: isDark ? Colors.white : Colors.black87,
                                fontSize: 14.5,
                                height: 1.35,
                                fontWeight: FontWeight.w500,
                              ),
                              decoration: InputDecoration(
                                hintText: 'Ask RIP anything...',
                                hintStyle: TextStyle(
                                  color: isDark ? Colors.white38 : Colors.black38,
                                  fontSize: 14.0,
                                ),
                                filled: false,
                                isDense: true,
                                border: InputBorder.none,
                                enabledBorder: InputBorder.none,
                                focusedBorder: InputBorder.none,
                                contentPadding: const EdgeInsets.symmetric(
                                  horizontal: 4,
                                  vertical: 4,
                                ),
                              ),
                              onSubmitted: (_) => widget.onSend(),
                            ),
                          ),
                          if (suffix.isNotEmpty)
                            Positioned(
                              right: 2,
                              top: 0,
                              child: GestureDetector(
                                onTap: () => _acceptSuggestion(suffix),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: AppColors.primary.withValues(alpha: 0.12),
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: AppColors.primary.withValues(alpha: 0.25)),
                                  ),
                                  child: Text(
                                    'Swipe → to complete',
                                    style: TextStyle(
                                      fontSize: 9.5,
                                      fontWeight: FontWeight.w600,
                                      color: AppColors.primary.withValues(alpha: 0.85),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Row 3: Bottom Tools & Actions Toolbar (Attach +, Effort Pill, Search, Slash Commands, Send Button)
                    Row(
                      children: [
                        _ComposerIconButton(
                          icon: Icons.add_rounded,
                          tooltip: 'Attach / Projects',
                          onPressed: () {
                            widget.controller.text = '@';
                            widget.controller.selection = TextSelection.collapsed(
                              offset: widget.controller.text.length,
                            );
                            widget.focusNode.requestFocus();
                          },
                        ),
                        const SizedBox(width: 6),
                        const _ComposerEffortPill(),
                        const SizedBox(width: 6),
                        _ComposerIconButton(
                          icon: Icons.search_rounded,
                          tooltip: 'Search Codebase',
                          onPressed: () {
                            widget.controller.text = 'search ';
                            widget.controller.selection = TextSelection.collapsed(
                              offset: widget.controller.text.length,
                            );
                            widget.focusNode.requestFocus();
                          },
                        ),
                        const SizedBox(width: 4),
                        _ComposerIconButton(
                          icon: Icons.terminal_rounded,
                          tooltip: 'Commands & Flags',
                          onPressed: () {
                            widget.controller.text = '/';
                            widget.controller.selection = TextSelection.collapsed(
                              offset: widget.controller.text.length,
                            );
                            widget.focusNode.requestFocus();
                          },
                        ),
                        const Spacer(),
                        widget.isBusy
                            ? _StopSendButton(onPressed: widget.onStop)
                            : _SendButton(onPressed: widget.onSend),
                      ],
                    ),
                  ],
                ),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.04),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.black.withValues(alpha: 0.08),
          ),
          borderRadius: BorderRadius.circular(16),
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
              padding: const EdgeInsets.fromLTRB(12, 7, 7, 7),
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
                        color: isDark ? Colors.white70 : Colors.black87,
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
                        backgroundColor: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
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
        onTap: () {
          HapticFeedback.lightImpact();
          onPressed();
        },
        child: Ink(
          width: 40,
          height: 40,
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
            size: 20,
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
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.error.withValues(alpha: 0.16),
            border: Border.all(color: AppColors.error.withValues(alpha: 0.38)),
          ),
          child: const Icon(
            Icons.stop_rounded,
            color: AppColors.error,
            size: 20,
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: tooltip,
      child: IconButton(
        onPressed: () {
          HapticFeedback.selectionClick();
          onPressed();
        },
        icon: Text(
          label,
          style: TextStyle(
            color: isDark ? Colors.white : Colors.black87,
            fontSize: 16,
            fontWeight: FontWeight.w900,
          ),
        ),
        style: IconButton.styleFrom(
          fixedSize: const Size(38, 38),
          backgroundColor: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.05),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
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
                color: isDark ? Colors.white54 : Colors.black54,
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
      crossAxisAlignment: CrossAxisAlignment.start,
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
          Padding(
            padding: const EdgeInsets.only(left: 2, bottom: 4),
            child: Text(
              'Optional Flags:',
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w600,
                color: isDark ? Colors.white54 : Colors.black54,
              ),
            ),
          ),
          _FlagChips(
            flags: flags,
            onSelected: _insertFlag,
          ),
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
    final valueStr = flag['value'] == 'true' ? '' : (flag['value'] != null ? ' ${flag['value']}' : '');
    final flagText = '$name$valueStr';
    final next = current.endsWith(' ') ? '$current$flagText ' : '$current $flagText ';
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Align(
      alignment: Alignment.centerLeft,
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (final flag in flags)
            Tooltip(
              message: flag['description']?.toString() ?? '',
              child: InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: () => onSelected(flag),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.08)
                        : Colors.black.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isDark
                          ? Colors.white.withValues(alpha: 0.12)
                          : Colors.black.withValues(alpha: 0.1),
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        flag['name'].toString(),
                        style: TextStyle(
                          color: isDark ? Colors.white70 : Colors.black87,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      if (flag['value'] != null) ...[
                        const SizedBox(width: 4),
                        Text(
                          flag['value'] == 'true' ? '(default: true)' : flag['value'].toString(),
                          style: TextStyle(
                            color: isDark ? Colors.white38 : Colors.black38,
                            fontSize: 10,
                            fontWeight: FontWeight.normal,
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Row(
      children: [
        Text(
          title,
          style: TextStyle(
            color: isDark ? Colors.white70 : Colors.black54,
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
            color: isDark ? Colors.white70 : Colors.black54,
            style: IconButton.styleFrom(
              fixedSize: const Size(32, 32),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              backgroundColor: isDark
                  ? Colors.white.withValues(alpha: 0.08)
                  : Colors.black.withValues(alpha: 0.05),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    if (children.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Text(
          emptyText,
          style: TextStyle(color: isDark ? Colors.white54 : Colors.black54),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Material(
      color: isDark
          ? Colors.white.withValues(alpha: 0.06)
          : Colors.black.withValues(alpha: 0.04),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(icon, size: 18, color: isDark ? Colors.white54 : Colors.black54),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: isDark ? Colors.white : Colors.black87,
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
                        color: isDark ? Colors.white54 : Colors.black54,
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
                  : '${project!.filesCount} files Â· ${project!.entitiesCount} entities Â· ${_primaryLanguage(project!)} Â· indexed ${_indexedLabel(project!)}',
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: tooltip,
      child: ClipOval(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.08)
                  : Colors.black.withValues(alpha: 0.05),
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.12)
                    : Colors.black.withValues(alpha: 0.1),
                width: 1,
              ),
              shape: BoxShape.circle,
            ),
            child: IconButton(
              icon: Icon(icon, size: 20),
              color: isDark ? Colors.white70 : Colors.black87,
              onPressed: onPressed,
            ),
          ),
        ),
      ),
    );
  }
}

class _EffortSelectorButton extends ConsumerWidget {
  const _EffortSelectorButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final effort = ref.watch(gatewayEffortProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return PopupMenuButton<String>(
      tooltip: 'Select Effort',
      offset: const Offset(0, 48),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.1),
        ),
      ),
      color: isDark ? const Color(0xFF13132B).withValues(alpha: 0.96) : Colors.white.withValues(alpha: 0.96),
      elevation: 0,
      onSelected: (val) {
        HapticFeedback.selectionClick();
        ref.read(gatewayEffortProvider.notifier).state = val;
      },
      itemBuilder: (context) => [
        _buildItem(context, 'auto', 'Auto', Icons.auto_awesome_rounded),
        _buildItem(context, 'fast', 'Fast', Icons.bolt_rounded),
        _buildItem(context, 'medium', 'Medium', Icons.speed_rounded),
        _buildItem(context, 'deep', 'Deep', Icons.query_stats_rounded),
      ],
      child: ClipOval(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isDark
                  ? Colors.white.withValues(alpha: 0.08)
                  : Colors.black.withValues(alpha: 0.05),
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.12)
                    : Colors.black.withValues(alpha: 0.1),
              ),
            ),
            child: Material(
              color: Colors.transparent,
              child: Center(
                child: Icon(
                  effort == 'fast'
                      ? Icons.bolt_rounded
                      : effort == 'medium'
                          ? Icons.speed_rounded
                          : effort == 'deep'
                              ? Icons.query_stats_rounded
                              : Icons.auto_awesome_rounded,
                  color: isDark ? Colors.white : Colors.black87,
                  size: 20,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  PopupMenuItem<String> _buildItem(
    BuildContext context,
    String value,
    String title,
    IconData icon,
  ) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return PopupMenuItem<String>(
      value: value,
      child: Row(
        children: [
          Icon(icon, size: 18, color: isDark ? Colors.white70 : Colors.black87),
          const SizedBox(width: 12),
          Text(
            title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white : Colors.black87,
            ),
          ),
        ],
      ),
    );
  }
}


class _ComposerIconButton extends StatelessWidget {
  const _ComposerIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: tooltip,
      child: Material(
        color: isDark
            ? Colors.white.withValues(alpha: 0.08)
            : Colors.black.withValues(alpha: 0.05),
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: () {
            HapticFeedback.selectionClick();
            onPressed();
          },
          child: Padding(
            padding: const EdgeInsets.all(7.0),
            child: Icon(
              icon,
              size: 18,
              color: isDark ? Colors.white70 : Colors.black87,
            ),
          ),
        ),
      ),
    );
  }
}

class _ComposerEffortPill extends ConsumerWidget {
  const _ComposerEffortPill();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final effort = ref.watch(gatewayEffortProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    final label = effort == 'fast'
        ? 'Fast'
        : effort == 'medium'
            ? 'Medium'
            : effort == 'deep'
                ? 'Deep'
                : 'Auto';

    final icon = effort == 'fast'
        ? Icons.bolt_rounded
        : effort == 'medium'
            ? Icons.speed_rounded
            : effort == 'deep'
                ? Icons.query_stats_rounded
                : Icons.auto_awesome_rounded;

    return PopupMenuButton<String>(
      tooltip: 'Select Effort Tier',
      offset: const Offset(0, -220),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(
          color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.1),
        ),
      ),
      color: isDark ? const Color(0xFF13132B).withValues(alpha: 0.96) : Colors.white.withValues(alpha: 0.96),
      elevation: 0,
      onSelected: (val) {
        HapticFeedback.selectionClick();
        ref.read(gatewayEffortProvider.notifier).state = val;
      },
      itemBuilder: (context) => [
        _buildItem(context, 'auto', 'Auto Effort', Icons.auto_awesome_rounded, 'Smart routing & execution'),
        _buildItem(context, 'fast', 'Fast Effort', Icons.bolt_rounded, 'Sub-100ms deterministic path'),
        _buildItem(context, 'medium', 'Medium Effort', Icons.speed_rounded, 'Balanced LLM reasoning'),
        _buildItem(context, 'deep', 'Deep Effort', Icons.query_stats_rounded, 'Exhaustive graph analysis'),
      ],
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isDark
                ? Colors.white.withValues(alpha: 0.12)
                : Colors.black.withValues(alpha: 0.08),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: AppColors.primary),
            const SizedBox(width: 5),
            Text(
              label,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w700,
                color: isDark ? Colors.white : Colors.black87,
              ),
            ),
       
          ],
        ),
      ),
    );
  }

  PopupMenuItem<String> _buildItem(
    BuildContext context,
    String value,
    String title,
    IconData icon,
    String subtitle,
  ) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return PopupMenuItem<String>(
      value: value,
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.primary),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: isDark ? Colors.white : Colors.black87,
                ),
              ),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 10.5,
                  color: isDark ? Colors.white54 : Colors.black54,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

