import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/design/app_colors.dart';
import '../providers/chat_provider.dart';
import '../providers/connection_provider.dart';
import '../providers/project_provider.dart';
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

    HapticFeedback.lightImpact();
    _textController.clear();
    setState(() => _composerExpanded = false);

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    await ref.read(chatProvider.notifier).sendMessage(text);
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
  }

  void _insertCommand(String command) {
    HapticFeedback.selectionClick();
    _textController.text = '$command ';
    _textController.selection = TextSelection.collapsed(
      offset: _textController.text.length,
    );
    _focusNode.requestFocus();
  }

  Future<void> _selectProject(String projectId) async {
    HapticFeedback.selectionClick();
    await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(projectId);
    _textController.clear();
    setState(() => _composerExpanded = false);
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(chatProvider);
    final activeProject = ref.watch(activeProjectProvider);
    final connectionStatus = ref.watch(connectionStatusProvider);
    final isAssistantBusy = ref.watch(isAssistantBusyProvider);

    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(),
      backgroundColor: AppColors.background,
      body: Builder(
        builder: (context) {
          return Stack(
            children: [
              const ColoredBox(color: AppColors.background),
              Column(
                children: [
                  Expanded(
                    child: messages.isEmpty
                        ? const _PremiumEmptyState()
                        : ListView.builder(
                            controller: _scrollController,
                            keyboardDismissBehavior:
                                ScrollViewKeyboardDismissBehavior.onDrag,
                            padding: const EdgeInsets.fromLTRB(0, 116, 0, 184),
                            itemCount: messages.length,
                            itemBuilder: (context, index) {
                              return TweenAnimationBuilder<double>(
                                tween: Tween(begin: 0, end: 1),
                                duration: Duration(
                                  milliseconds: 220 + (index % 4) * 34,
                                ),
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
                                child: ChatBubble(message: messages[index]),
                              );
                            },
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
                  context.go('/setup');
                },
                activeProjectName: activeProject.maybeWhen(
                  data: (project) => project?.projectName,
                  orElse: () => null,
                ),
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
              Align(
                alignment: Alignment.bottomCenter,
                child: _FloatingComposer(
                  controller: _textController,
                  focusNode: _focusNode,
                  expanded: _composerExpanded,
                  isBusy: isAssistantBusy,
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

class _FloatingHeader extends StatelessWidget {
  const _FloatingHeader({
    required this.progress,
    required this.onMenuTap,
    required this.onSettingsTap,
    required this.activeProjectName,
  });

  final double progress;
  final VoidCallback onMenuTap;
  final VoidCallback onSettingsTap;
  final String? activeProjectName;

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;
    final height = lerpDouble(82, 66, progress)!;
    final veilAlpha = lerpDouble(0.70, 0.94, progress)!;
    final midFadeAlpha = lerpDouble(0.34, 0.62, progress)!;
    final tailFadeAlpha = lerpDouble(0.08, 0.22, progress)!;
    final blurSigma = lerpDouble(2, 10, progress)!;

    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: SizedBox(
        height: top + height + 58,
        child: Stack(
          children: [
            Positioned.fill(
              child: IgnorePointer(
                child: ClipRect(
                  child: BackdropFilter(
                    filter: ImageFilter.blur(
                      sigmaX: blurSigma,
                      sigmaY: blurSigma,
                    ),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: const [0, 0.43, 0.66, 0.84, 1],
                          colors: [
                            AppColors.background.withValues(alpha: veilAlpha),
                            AppColors.background
                                .withValues(alpha: veilAlpha * 0.94),
                            AppColors.background.withValues(alpha: midFadeAlpha),
                            AppColors.background.withValues(alpha: tailFadeAlpha),
                            AppColors.background.withValues(alpha: 0),
                          ],
                        ),
                      ),
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
                            const Text(
                              'AI Assistant',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 17,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            AnimatedSwitcher(
                              duration: const Duration(milliseconds: 180),
                              child: activeProjectName == null
                                  ? const SizedBox(height: 2)
                                  : Text(
                                      activeProjectName!,
                                      key: ValueKey(activeProjectName),
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

class _FloatingComposer extends StatelessWidget {
  const _FloatingComposer({
    required this.controller,
    required this.focusNode,
    required this.expanded,
    required this.isBusy,
    required this.onSend,
    required this.onStop,
    required this.onCommandSelected,
    required this.onProjectSelected,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool expanded;
  final bool isBusy;
  final VoidCallback onSend;
  final VoidCallback onStop;
  final ValueChanged<String> onCommandSelected;
  final ValueChanged<String> onProjectSelected;

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    final hasFocus = focusNode.hasFocus;

    return Padding(
      padding: EdgeInsets.fromLTRB(18, 0, 18, bottom + 30),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(expanded ? 26 : 28),
          border: Border.all(
            color: hasFocus
                ? AppColors.primary.withValues(alpha: 0.56)
                : Colors.white.withValues(alpha: 0.08),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.42),
              blurRadius: 36,
              offset: const Offset(0, 20),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(expanded ? 26 : 28),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: AppColors.surface.withValues(alpha: 0.98),
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
                          icon: Icons.add_rounded,
                          tooltip: 'Attach',
                          onPressed: () {},
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
                                hintText: 'Ask RIP anything',
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
                          icon: Icons.graphic_eq_rounded,
                          tooltip: 'Voice',
                          onPressed: () {},
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
    return ClipRRect(
      borderRadius: BorderRadius.circular(18),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.055),
          border: Border.all(color: Colors.white.withValues(alpha: 0.075)),
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
                      'RIP is working. Long commands can take a while.',
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
                        backgroundColor: Colors.white.withValues(alpha: 0.06),
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
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: IconButton(
        onPressed: () {
          HapticFeedback.selectionClick();
          onPressed();
        },
        icon: Icon(icon, color: AppColors.textSecondary, size: 22),
        style: IconButton.styleFrom(
          fixedSize: const Size(42, 42),
          backgroundColor: Colors.white.withValues(alpha: 0.05),
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

    final filter = text.startsWith('/') ? text.substring(1).toLowerCase() : '';
    final commands = CommandParser.getAvailableCommands()
        .where((command) =>
            command['name'].toLowerCase().contains(filter) ||
            command['description'].toLowerCase().contains(filter))
        .take(6)
        .toList();
    return _SuggestionList(
      emptyText: 'No commands found',
      children: [
        for (final command in commands)
          _SuggestionRow(
            icon: Icons.terminal_rounded,
            title: command['name'],
            subtitle: command['description'],
            onTap: () => onCommandSelected(command['name']),
          ),
      ],
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

class _SuggestionHeader extends StatelessWidget {
  const _SuggestionHeader({
    required this.title,
    required this.onRefresh,
  });

  final String title;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
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
              backgroundColor: Colors.white.withValues(alpha: 0.05),
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
    return Material(
      color: Colors.white.withValues(alpha: 0.055),
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
  const _PremiumEmptyState();

  @override
  Widget build(BuildContext context) {
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
                color: AppColors.surfaceVariant,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.28),
                    blurRadius: 46,
                    offset: const Offset(0, 18),
                  ),
                ],
              ),
              child: const Icon(
                Icons.auto_awesome_rounded,
                color: Colors.white,
                size: 42,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'What are we building today?',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 25,
                height: 1.12,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Ask about code, architecture, impact, dependencies, or the next change.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.textSecondary.withValues(alpha: 0.78),
                fontSize: 14,
                height: 1.45,
              ),
            ),
          ],
        ),
      ),
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
    return Tooltip(
      message: tooltip,
      child: ClipOval(
        child: Material(
          color: Colors.white.withValues(alpha: 0.08),
          shape: CircleBorder(
            side: BorderSide(color: Colors.white.withValues(alpha: 0.09)),
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
